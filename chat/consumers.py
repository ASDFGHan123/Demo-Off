import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from .models import Message, Conversation, Attachment, Reaction, User
from .permissions import conversation_access_required

# Set up logging
logger = logging.getLogger(__name__)


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        try:
            self.room_name = self.scope['url_route']['kwargs']['room_name']
            self.room_group_name = f'chat_{self.room_name}'

            # Check if user is authenticated
            if not self.scope['user'].is_authenticated:
                logger.warning(f"Unauthenticated user attempted to connect to room {self.room_name}")
                await self.close()
                return

            user = self.scope['user']

            # Check if user has permission to view chat
            if not user.has_perm('view_chat'):
                logger.warning(f"User {user.username} does not have permission to view chat")
                await self.close()
                return

            # Check if conversation exists and user can access it
            try:
                conversation = await sync_to_async(Conversation.objects.get)(conversation_id=self.room_name)
                if not user.can_access_conversation(conversation):
                    logger.warning(f"User {user.username} attempted to connect to unauthorized room {self.room_name}")
                    await self.close()
                    return
            except Conversation.DoesNotExist:
                logger.warning(f"User {self.scope['user'].username} attempted to connect to non-existent room {self.room_name}")
                await self.close()
                return

            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # Set user online status
            await self.set_user_online(user, True)

            # Broadcast online status to participants
            await self.broadcast_online_status(conversation, user, True)

            # Deliver pending messages to the user
            await self.deliver_pending_messages(user, conversation)

            logger.info(f"User {user.username} connected to room {self.room_name}")
            await self.accept()
        except Exception as e:
            logger.error(f"Error connecting user to room {self.room_name}: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        try:
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

            # Set user offline status
            user = self.scope['user']
            await self.set_user_online(user, False)

            # Broadcast offline status to participants
            try:
                conversation = await sync_to_async(Conversation.objects.get)(conversation_id=self.room_name)
                await self.broadcast_online_status(conversation, user, False)
            except Conversation.DoesNotExist:
                logger.warning(f"Conversation {self.room_name} not found during disconnect")

            logger.info(f"User {user.username} disconnected from room {self.room_name} with code {close_code}")
        except Exception as e:
            logger.error(f"Error disconnecting user from room {self.room_name}: {str(e)}")

    # Receive message from WebSocket
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type', 'message')

            if message_type == 'reaction':
                await self.handle_reaction(text_data_json)
            elif message_type == 'read_receipt':
                await self.handle_read_receipt(text_data_json)
            elif message_type == 'edit_message':
                await self.handle_edit_message(text_data_json)
            elif message_type == 'delete_message':
                await self.handle_delete_message(text_data_json)
            else:
                message_content = text_data_json.get('message', '').strip()
                attachment_data = text_data_json.get('attachment')
                reply_to_id = text_data_json.get('reply_to')
                user = self.scope['user']

                # Validate message content
                if not message_content and not attachment_data:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Message cannot be empty'
                    }))
                    return

                if len(message_content) > 1000:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Message is too long (max 1000 characters)'
                    }))
                    return

                # Check if user can send messages in this conversation
                conversation = await sync_to_async(Conversation.objects.get)(conversation_id=self.room_name)
                if not user.can_send_message(conversation):
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'You do not have permission to send messages in this conversation'
                    }))
                    return

                # Save message to database
                message = await self.save_message(message_content, user, self.room_name, attachment_data, reply_to_id)

                # Get reactions for the message
                reactions = await self.get_message_reactions(message.message_id)

                # Send message to room group
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message_content,
                        'user': user.username,
                        'user_id': user.user_id,
                        'timestamp': str(message.sent_at),
                        'attachment': attachment_data,
                        'message_id': message.message_id,
                        'reply_to': reply_to_id,
                        'reply_to_sender': message.reply_to.sender.username if message.reply_to else None,
                        'reply_to_content': message.reply_to.content if message.reply_to else None,
                        'reactions': reactions,
                    }
                )

                # Send notification to other participants
                await self.send_notification_to_participants(conversation, user, message_content)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received from user {self.scope['user'].username} in room {self.room_name}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid message format'
            }))
        except Exception as e:
            logger.error(f"Error processing message from user {self.scope['user'].username} in room {self.room_name}: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to send message. Please try again.'
            }))

    # Receive message from room group
    async def chat_message(self, event):
        message = event['message']
        user = event['user']
        user_id = event['user_id']
        timestamp = event['timestamp']
        attachment = event.get('attachment')
        message_id = event.get('message_id')
        reply_to = event.get('reply_to')
        reply_to_sender = event.get('reply_to_sender')
        reply_to_content = event.get('reply_to_content')
        reactions = event.get('reactions')

        # Update message status to delivered for this user (if exists)
        current_user = self.scope['user']
        if current_user.user_id != user_id:  # Don't update for sender
            await self.update_message_delivered(message_id, current_user)

        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            'message': message,
            'user': user,
            'user_id': user_id,
            'timestamp': timestamp,
            'attachment': attachment,
            'message_id': message_id,
            'reply_to': reply_to,
            'reply_to_sender': reply_to_sender,
            'reply_to_content': reply_to_content,
            'reactions': reactions,
        }))

    # Handle reaction
    async def handle_reaction(self, data):
        try:
            message_id = data.get('message_id')
            emoji = data.get('emoji')
            user = self.scope['user']

            if not message_id or not emoji:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message ID and emoji are required'
                }))
                return

            # Validate emoji (basic check)
            if len(emoji) > 10:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Invalid emoji'
                }))
                return

            # Check if user can access the message's conversation
            try:
                message = await sync_to_async(Message.objects.get)(message_id=message_id)
                if not user.can_access_conversation(message.conversation):
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'You do not have access to this message'
                    }))
                    return
            except Message.DoesNotExist:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message not found'
                }))
                return

            # Save or remove reaction
            reaction = await self.save_or_remove_reaction(message_id, user, emoji)

            # Get updated reactions
            reactions = await self.get_message_reactions(message_id)

            # Send reaction update to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'reaction_update',
                    'message_id': message_id,
                    'reactions': reactions,
                }
            )
        except Exception as e:
            logger.error(f"Error handling reaction from user {self.scope['user'].username}: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to process reaction. Please try again.'
            }))

    # Receive reaction update from room group
    async def reaction_update(self, event):
        message_id = event['message_id']
        reactions = event['reactions']

        # Send reaction update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'message_id': message_id,
            'reactions': reactions,
        }))

    # Receive user status update from room group
    async def user_status_update(self, event):
        user_id = event['user_id']
        username = event['username']
        is_online = event['is_online']

        # Send status update to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'user_status',
            'user_id': user_id,
            'username': username,
            'is_online': is_online,
        }))

    # Receive notification from room group
    async def notification(self, event):
        sender = event['sender']
        message = event['message']
        conversation_id = event['conversation_id']
        conversation_title = event['conversation_title']

        # Send notification to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'sender': sender,
            'message': message,
            'conversation_id': conversation_id,
            'conversation_title': conversation_title,
        }))

    # Receive read receipt from room group
    async def read_receipt(self, event):
        message_id = event['message_id']
        user_id = event['user_id']
        username = event['username']

        # Send read receipt to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'read_receipt',
            'message_id': message_id,
            'user_id': user_id,
            'username': username,
        }))

    # Receive message edit from room group
    async def message_edited(self, event):
        message_id = event['message_id']
        content = event['content']
        edited_by = event['edited_by']

        # Send message edit to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message_edited',
            'message_id': message_id,
            'content': content,
            'edited_by': edited_by,
        }))

    # Receive message deletion from room group
    async def message_deleted(self, event):
        message_id = event['message_id']
        deleted_by = event['deleted_by']

        # Send message deletion to WebSocket
        await self.send(text_data=json.dumps({
            'type': 'message_deleted',
            'message_id': message_id,
            'deleted_by': deleted_by,
        }))

    @sync_to_async
    def save_message(self, content, user, room_name, attachment_data=None, reply_to_id=None):
        from .models import MessageStatus
        try:
            conversation = Conversation.objects.get(conversation_id=room_name)
            reply_to = None
            if reply_to_id:
                try:
                    reply_to = Message.objects.get(message_id=reply_to_id)
                except Message.DoesNotExist:
                    logger.warning(f"Reply to message {reply_to_id} not found")

            message = Message.objects.create(
                conversation=conversation,
                sender=user,
                content=content,
                reply_to=reply_to,
            )

            if attachment_data:
                # Create attachment record
                attachment = Attachment.objects.create(
                    message=message,
                    file_name=attachment_data['name'],
                    mime_type=attachment_data['type'],
                    file_size=attachment_data['size'],
                )
                # Note: file field will be set via a separate upload endpoint

            # Create message status for all participants except sender
            participants = self.get_conversation_participants(conversation)
            for participant in participants:
                if participant != user:
                    MessageStatus.objects.create(
                        message=message,
                        user=participant,
                        status='sent'
                    )

            return message
        except Conversation.DoesNotExist:
            logger.error(f"Conversation {room_name} not found when saving message")
            raise
        except Exception as e:
            logger.error(f"Error saving message to conversation {room_name}: {str(e)}")
            raise

    @sync_to_async
    def save_or_remove_reaction(self, message_id, user, emoji):
        try:
            message = Message.objects.get(message_id=message_id)
            reaction, created = Reaction.objects.get_or_create(
                message=message,
                user=user,
                emoji=emoji,
                defaults={'created_at': None}  # Will use auto_now_add
            )
            if not created:
                # If reaction already exists, remove it (toggle behavior)
                reaction.delete()
                return None
            return reaction
        except Message.DoesNotExist:
            logger.warning(f"Message {message_id} not found when saving reaction")
            return None
        except Exception as e:
            logger.error(f"Error saving reaction to message {message_id}: {str(e)}")
            return None

    @sync_to_async
    def get_message_reactions(self, message_id):
        try:
            message = Message.objects.get(message_id=message_id)
            reactions = list(message.reaction_set.values('emoji', 'user__username'))
            # Group reactions by emoji and collect users
            reaction_dict = {}
            for reaction in reactions:
                emoji = reaction['emoji']
                user = reaction['user__username']
                if emoji not in reaction_dict:
                    reaction_dict[emoji] = []
                reaction_dict[emoji].append(user)

            # Format for frontend
            formatted_reactions = []
            for emoji, users in reaction_dict.items():
                formatted_reactions.append({
                    'emoji': emoji,
                    'users': users,
                    'count': len(users)
                })
            return formatted_reactions
        except Message.DoesNotExist:
            logger.warning(f"Message {message_id} not found when getting reactions")
            return []
        except Exception as e:
            logger.error(f"Error getting reactions for message {message_id}: {str(e)}")
            return []

    @sync_to_async
    def set_user_online(self, user, is_online):
        try:
            user.is_online = is_online
            user.save(update_fields=['is_online'])
            logger.info(f"User {user.username} set to {'online' if is_online else 'offline'}")
        except Exception as e:
            logger.error(f"Error setting online status for user {user.username}: {str(e)}")

    async def broadcast_online_status(self, conversation, user, is_online):
        try:
            participants = await self.get_conversation_participants(conversation)
            # Broadcast to all participants except the user themselves
            for participant in participants:
                if participant != user:
                    # Send to participant's room group if they are connected
                    participant_room_group = f'chat_{conversation.conversation_id}'
                    await self.channel_layer.group_send(
                        participant_room_group,
                        {
                            'type': 'user_status_update',
                            'user_id': user.user_id,
                            'username': user.username,
                            'is_online': is_online,
                        }
                    )
        except Exception as e:
            logger.error(f"Error broadcasting online status for user {user.username}: {str(e)}")

    @sync_to_async
    def get_conversation_participants(self, conversation):
        try:
            participants = []
            if conversation.type == 'private':
                private_chat = conversation.privatechat
                participants = [private_chat.user1, private_chat.user2]
            elif conversation.type == 'group':
                participants = [member.user for member in conversation.groupchat.groupmember_set.all()]
            return participants
        except Exception as e:
            logger.error(f"Error getting participants for conversation {conversation.conversation_id}: {str(e)}")
            return []

    @sync_to_async
    def is_user_participant(self, conversation, user):
        try:
            if conversation.type == 'private':
                private_chat = conversation.privatechat
                return private_chat.user1 == user or private_chat.user2 == user
            elif conversation.type == 'group':
                return conversation.groupchat.groupmember_set.filter(user=user).exists()
            return False
        except Exception as e:
            logger.error(f"Error checking user participation for conversation {conversation.conversation_id}: {str(e)}")
            return False

    async def send_notification_to_participants(self, conversation, sender, message_content):
        try:
            participants = await self.get_conversation_participants(conversation)
            for participant in participants:
                if participant != sender and participant.enable_notifications:
                    # Send notification via WebSocket if user is connected to this conversation
                    participant_room_group = f'chat_{conversation.conversation_id}'
                    await self.channel_layer.group_send(
                        participant_room_group,
                        {
                            'type': 'notification',
                            'sender': sender.username,
                            'message': message_content[:50] + ('...' if len(message_content) > 50 else ''),
                            'conversation_id': conversation.conversation_id,
                            'conversation_title': conversation.title or f"Chat with {sender.display_name}",
                        }
                    )
        except Exception as e:
            logger.error(f"Error sending notification for conversation {conversation.conversation_id}: {str(e)}")

    async def handle_read_receipt(self, data):
        try:
            message_id = data.get('message_id')
            user = self.scope['user']

            if not message_id:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message ID is required'
                }))
                return

            # Update message status to read
            await self.update_message_read_status(message_id, user)

            # Broadcast read receipt to other participants
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'message_id': message_id,
                    'user_id': user.user_id,
                    'username': user.username,
                }
            )
        except Exception as e:
            logger.error(f"Error handling read receipt from user {self.scope['user'].username}: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to process read receipt. Please try again.'
            }))

    async def handle_edit_message(self, data):
        try:
            message_id = data.get('message_id')
            new_content = data.get('content', '').strip()
            user = self.scope['user']

            if not message_id or not new_content:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message ID and content are required'
                }))
                return

            # Validate message length
            if len(new_content) > 1000:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message is too long (max 1000 characters)'
                }))
                return

            # Check if user can edit this message
            message = await sync_to_async(Message.objects.get)(message_id=message_id)
            if not user.can_edit_message(message):
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You do not have permission to edit this message'
                }))
                return

            # Update message
            await self.update_message_content(message_id, new_content, user)

            # Broadcast edit to all participants
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_edited',
                    'message_id': message_id,
                    'content': new_content,
                    'edited_by': user.username,
                }
            )
        except Message.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Message not found'
            }))
        except Exception as e:
            logger.error(f"Error editing message from user {self.scope['user'].username}: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to edit message. Please try again.'
            }))

    async def handle_delete_message(self, data):
        try:
            message_id = data.get('message_id')
            user = self.scope['user']

            if not message_id:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Message ID is required'
                }))
                return

            # Check if user can delete this message
            message = await sync_to_async(Message.objects.get)(message_id=message_id)
            if not user.can_delete_message(message):
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You do not have permission to delete this message'
                }))
                return

            # Soft delete message
            await self.delete_message_content(message_id, user)

            # Broadcast deletion to all participants
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'message_deleted',
                    'message_id': message_id,
                    'deleted_by': user.username,
                }
            )
        except Message.DoesNotExist:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Message not found'
            }))
        except Exception as e:
            logger.error(f"Error deleting message from user {self.scope['user'].username}: {str(e)}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Failed to delete message. Please try again.'
            }))

    @sync_to_async
    def update_message_read_status(self, message_id, user):
        from .models import MessageStatus
        try:
            MessageStatus.objects.filter(
                message_id=message_id,
                user=user
            ).update(status='read')
            logger.info(f"User {user.username} marked message {message_id} as read")
        except Exception as e:
            logger.error(f"Error updating read status for message {message_id}: {str(e)}")

    @sync_to_async
    def update_message_delivered(self, message_id, user):
        from .models import MessageStatus
        try:
            MessageStatus.objects.filter(
                message_id=message_id,
                user=user,
                status='sent'
            ).update(status='delivered')
            logger.info(f"User {user.username} received message {message_id}")
        except Exception as e:
            logger.error(f"Error updating delivered status for message {message_id}: {str(e)}")

    @sync_to_async
    def update_message_content(self, message_id, new_content, user):
        try:
            message = Message.objects.get(message_id=message_id)
            message.content = new_content
            message.is_edited = True
            message.edited_at = None  # Will use auto_now
            message.save(update_fields=['content', 'is_edited', 'edited_at'])
            logger.info(f"User {user.username} edited message {message_id}")
        except Message.DoesNotExist:
            logger.warning(f"Message {message_id} not found when editing")
        except Exception as e:
            logger.error(f"Error updating message content for {message_id}: {str(e)}")
            raise

    @sync_to_async
    def delete_message_content(self, message_id, user):
        try:
            message = Message.objects.get(message_id=message_id)
            message.is_deleted = True
            message.deleted_at = None  # Will use auto_now
            message.save(update_fields=['is_deleted', 'deleted_at'])
            logger.info(f"User {user.username} deleted message {message_id}")
        except Message.DoesNotExist:
            logger.warning(f"Message {message_id} not found when deleting")
        except Exception as e:
            logger.error(f"Error deleting message {message_id}: {str(e)}")
            raise

    async def deliver_pending_messages(self, user, conversation):
        from .models import MessageStatus
        try:
            # Get all messages in this conversation that the user hasn't read yet
            pending_messages = await sync_to_async(list)(
                Message.objects.filter(
                    conversation=conversation,
                    messagestatus__user=user,
                    messagestatus__status__in=['sent', 'delivered']
                ).select_related('sender').prefetch_related('reaction_set').order_by('sent_at')
            )

            for message in pending_messages:
                # Update status to delivered
                await sync_to_async(
                    MessageStatus.objects.filter(
                        message=message,
                        user=user
                    ).update
                )(status='delivered')

                # Get reactions for the message
                reactions = await self.get_message_reactions(message.message_id)

                # Send the message to the user
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message.content,
                        'user': message.sender.username,
                        'user_id': message.sender.user_id,
                        'timestamp': str(message.sent_at),
                        'attachment': None,  # Pending messages don't have attachments in this implementation
                        'message_id': message.message_id,
                        'reply_to': message.reply_to.message_id if message.reply_to else None,
                        'reply_to_sender': message.reply_to.sender.username if message.reply_to else None,
                        'reply_to_content': message.reply_to.content if message.reply_to else None,
                        'reactions': reactions,
                    }
                )

            logger.info(f"Delivered {len(pending_messages)} pending messages to user {user.username} in conversation {conversation.conversation_id}")
        except Exception as e:
            logger.error(f"Error delivering pending messages to user {user.username}: {str(e)}")