from .permissions import permission_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.db import models
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
import json
import logging
from .models import User, Conversation, Message, AuditLog, PrivateChat, GroupChat, GroupMember, Role, UserRole, Attachment

logger = logging.getLogger(__name__)

@permission_required('view_admin_panel')
def admin_panel(request):
    try:
        # Get basic stats
        total_users = User.objects.count()
        total_conversations = Conversation.objects.count()
        total_messages = Message.objects.count()

        # Get recent audit logs
        recent_logs = AuditLog.objects.select_related('actor').order_by('-timestamp')[:50]

        context = {
            'total_users': total_users,
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'recent_logs': recent_logs,
        }

        return render(request, 'chat/admin_panel.html', context)
    except Exception as e:
        logger.error(f"Error loading admin panel for user {request.user.username}: {str(e)}")
        return render(request, 'chat/500.html', status=500)
    
@permission_required('manage_users')
def manage_users(request):
    try:
        users = User.objects.all().order_by('-created_at')
        return render(request, 'chat/manage_users.html', {'users': users})
    except Exception as e:
        logger.error(f"Error loading user management for user {request.user.username}: {str(e)}")
        return render(request, 'chat/500.html', status=500)

@permission_required('manage_roles')
def assign_user_role(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        role_name = data.get('role_name')

        if not user_id or not role_name:
            return JsonResponse({'status': 'error', 'message': 'User ID and role name are required'})

        try:
            target_user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'})

        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Role not found'})

        # Check if user already has this role
        if UserRole.objects.filter(user=target_user, role=role).exists():
            return JsonResponse({'status': 'error', 'message': 'User already has this role'})

        # Assign role
        UserRole.objects.create(user=target_user, role=role)

        # Log the action
        AuditLog.objects.create(
            actor=request.user,
            action='update',
            target_type='user',
            target_id=target_user.user_id,
            old_value='',
            new_value=f'Assigned role: {role_name}',
            ip_address=get_client_ip(request)
        )

        logger.info(f"User {request.user.username} assigned role {role_name} to {target_user.username}")
        return JsonResponse({'status': 'success', 'message': f'Role {role_name} assigned to {target_user.display_name}'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error assigning role by user {request.user.username}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Failed to assign role'}, status=500)

@permission_required('manage_roles')
def remove_user_role(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        role_name = data.get('role_name')

        if not user_id or not role_name:
            return JsonResponse({'status': 'error', 'message': 'User ID and role name are required'})

        try:
            target_user = User.objects.get(user_id=user_id)
        except User.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'User not found'})

        try:
            role = Role.objects.get(name=role_name)
        except Role.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Role not found'})

        # Remove role
        UserRole.objects.filter(user=target_user, role=role).delete()

        # Log the action
        AuditLog.objects.create(
            actor=request.user,
            action='update',
            target_type='user',
            target_id=target_user.user_id,
            old_value=f'Removed role: {role_name}',
            new_value='',
            ip_address=get_client_ip(request)
        )

        logger.info(f"User {request.user.username} removed role {role_name} from {target_user.username}")
        return JsonResponse({'status': 'success', 'message': f'Role {role_name} removed from {target_user.display_name}'})

    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    except Exception as e:
        logger.error(f"Error removing role by user {request.user.username}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Failed to remove role'}, status=500)

@permission_required('view_audit_logs')
def audit_logs(request):
    try:
        logs = AuditLog.objects.select_related('actor').order_by('-timestamp')

        # Filter by date range if provided
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        if start_date:
            logs = logs.filter(timestamp__gte=start_date)
        if end_date:
            logs = logs.filter(timestamp__lte=end_date)

        # Filter by action type if provided
        action = request.GET.get('action')
        if action:
            logs = logs.filter(action=action)

        # Paginate results
        from django.core.paginator import Paginator
        paginator = Paginator(logs, 50)  # 50 logs per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        return render(request, 'chat/audit_logs.html', {
            'page_obj': page_obj,
            'actions': AuditLog.ACTION_CHOICES,
            'targets': AuditLog.TARGET_TYPES
        })
    except Exception as e:
        logger.error(f"Error loading audit logs for user {request.user.username}: {str(e)}")
        return render(request, 'chat/500.html', status=500)

@permission_required('delete_conversations')
def delete_conversation(request, conversation_id):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)

        # Log the action before deletion
        AuditLog.objects.create(
            actor=request.user,
            action='delete',
            target_type='conversation',
            target_id=conversation.conversation_id,
            old_value=f'Deleted conversation: {conversation.title or "Untitled"}',
            new_value='',
            ip_address=get_client_ip(request)
        )

        # Delete the conversation (this will cascade delete related objects)
        conversation.delete()

        logger.info(f"User {request.user.username} deleted conversation {conversation_id}")
        return JsonResponse({'status': 'success', 'message': 'Conversation deleted successfully'})

    except Conversation.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Conversation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error deleting conversation {conversation_id} by user {request.user.username}: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Failed to delete conversation'}, status=500)

def get_client_ip(request):
    """Get the client IP address from the request."""
class LoginView(View):
    def get(self, request):
        return render(request, 'chat/login.html')

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('chat_list')
        messages.error(request, 'Invalid credentials')
        return render(request, 'chat/login.html')

class RegisterView(View):
    def get(self, request):
        return render(request, 'chat/register.html')

    def post(self, request):
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        display_name = request.POST.get('display_name')

        # Check for existing username
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username taken')
            return render(request, 'chat/register.html')

        # Check for existing email only if email is provided
        if email and User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered')
            return render(request, 'chat/register.html')

        try:
            user = User.objects.create_user(username=username, email=email if email else None, password=password, display_name=display_name)

            # Automatically assign 'user' role to new users
            try:
                from .models import Role, UserRole
                user_role = Role.objects.get(name='user')
                UserRole.objects.create(user=user, role=user_role)
            except Role.DoesNotExist:
                logger.warning("Default 'user' role not found. User created without role assignment.")
            except Exception as e:
                logger.error(f"Error assigning default role to user {username}: {str(e)}")

            login(request, user)
            return redirect('chat_list')
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            messages.error(request, 'Registration failed. Please try again.')
            return render(request, 'chat/register.html')

@login_required
def chat_list(request):
    conversations = get_user_conversations(request.user)
    return render(request, 'chat/chat_list.html', {'conversations': conversations})

@login_required
def chat_detail(request, conversation_id):
    try:
        conversation = Conversation.objects.get(conversation_id=conversation_id)

        # Check if user has access to this conversation
        if not request.user.can_access_conversation(conversation):
            # Check if user is authenticated but not a member
            if request.user.is_authenticated:
                error_message = 'You are not a member of this conversation'
            else:
                error_message = 'You must be logged in to access this conversation'
            return render(request, 'chat/access_denied.html', {
                'conversation': conversation,
                'error_message': error_message
            })

        messages_list = Message.objects.filter(conversation=conversation).select_related('sender').prefetch_related('reaction_set').order_by('sent_at')
        return render(request, 'chat/chat_detail.html', {'conversation': conversation, 'messages': messages_list})

    except Conversation.DoesNotExist:
        messages.error(request, 'Conversation not found')
        return redirect('chat_list')
    except Exception as e:
        logger.error(f"Error loading chat {conversation_id} for user {request.user.username}: {str(e)}")
        messages.error(request, 'Failed to load conversation')
        return redirect('chat_list')

@login_required
def create_private_chat(request):
    if request.method == 'POST':
        other_user_id = request.POST.get('selected_user')
        try:
            other_user = User.objects.get(user_id=other_user_id)

            # Check if chat already exists
            existing_chat = Conversation.objects.filter(
                type='private',
                privatechat__user1__in=[request.user, other_user],
                privatechat__user2__in=[request.user, other_user]
            ).first()

            if existing_chat:
                return redirect('chat_detail', conversation_id=existing_chat.conversation_id)

            # Create new conversation and private chat
            conversation = Conversation.objects.create(type='private')
            PrivateChat.objects.create(
                conversation=conversation,
                user1=min(request.user, other_user, key=lambda u: u.user_id),
                user2=max(request.user, other_user, key=lambda u: u.user_id)
            )

            return redirect('chat_detail', conversation_id=conversation.conversation_id)

        except User.DoesNotExist:
            messages.error(request, 'The selected user could not be found. They may have been removed from the system.')
        except Exception as e:
            logger.error(f"Error creating private chat: {str(e)}")
            messages.error(request, 'Unable to create chat at this time. Please try again later.')

    # Get users excluding current user
    users = User.objects.exclude(user_id=request.user.user_id)
    return render(request, 'chat/create_private_chat.html', {'users': users})

@login_required
def create_group_chat(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        description = request.POST.get('description')
        member_ids = request.POST.getlist('members')

        if not title:
            messages.error(request, 'Group title is required')
            return render(request, 'chat/create_group_chat.html')

        try:
            # Create conversation and group chat
            conversation = Conversation.objects.create(type='group', title=title)
            group_chat = GroupChat.objects.create(
                conversation=conversation,
                created_by=request.user,
                description=description
            )

            # Add creator as admin
            GroupMember.objects.create(
                group_chat=group_chat,
                user=request.user,
                role='admin'
            )

            # Add selected members
            for member_id in member_ids:
                try:
                    member = User.objects.get(user_id=member_id)
                    if member != request.user:  # Don't add creator twice
                        GroupMember.objects.create(
                            group_chat=group_chat,
                            user=member,
                            role='member'
                        )
                except User.DoesNotExist:
                    continue

            return redirect('chat_detail', conversation_id=conversation.conversation_id)

        except Exception as e:
            logger.error(f"Error creating group chat: {str(e)}")
            messages.error(request, 'Failed to create group chat')

    # Get users excluding current user
    users = User.objects.exclude(user_id=request.user.user_id)
    return render(request, 'chat/create_group_chat.html', {'users': users})

@login_required
def user_search(request):
    query = request.GET.get('q', '').strip()
    results = []

    if query:
        # Search by username or display name
        users = User.objects.filter(
            models.Q(username__icontains=query) |
            models.Q(display_name__icontains=query)
        ).exclude(user_id=request.user.user_id)[:10]

        results = [{
            'user_id': user.user_id,
            'username': user.username,
            'display_name': user.display_name,
            'profile_image_url': user.profile_image_url,
            'is_online': user.is_online
        } for user in users]

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'results': results})

    return render(request, 'chat/user_search.html', {'results': results, 'query': query})

class SendMessageView(View):
    def post(self, request, conversation_id):
        try:
            content = request.POST.get('content', '').strip()
            reply_to_id = request.POST.get('reply_to')

            if not content:
                return JsonResponse({'status': 'error', 'message': 'Message content is required'})

            # Verify conversation access
            conversation = Conversation.objects.get(conversation_id=conversation_id)
            if not request.user.can_access_conversation(conversation):
                return JsonResponse({'status': 'error', 'message': 'You do not have permission to send messages in this conversation'})

            # Create message
            message = Message.objects.create(
                conversation_id=conversation_id,
                sender=request.user,
                content=content,
                reply_to_id=reply_to_id if reply_to_id else None
            )

            return JsonResponse({
                'status': 'ok',
                'message_id': message.message_id,
                'message': {
                    'id': message.message_id,
                    'content': message.content,
                    'sender': message.sender.display_name,
                    'sent_at': message.sent_at.isoformat(),
                    'reply_to': message.reply_to.message_id if message.reply_to else None
                }
            })

            # Send real-time notification via WebSocket
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync

            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'chat_{conversation_id}',
                {
                    'type': 'chat_message',
                    'message': content,
                    'user': request.user.username,
                    'user_id': request.user.user_id,
                    'timestamp': str(message.sent_at),
                    'message_id': message.message_id,
                    'reply_to': reply_to_id,
                }
            )

        except Conversation.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Conversation not found'})
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'Failed to send message'})

@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def upload_attachment(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'})

    try:
        file = request.FILES.get('file')
        message_id = request.POST.get('message_id')

        if not file:
            return JsonResponse({'status': 'error', 'message': 'No file provided'})

        if not message_id:
            return JsonResponse({'status': 'error', 'message': 'Message ID required'})

        # Verify message ownership
        message = Message.objects.get(message_id=message_id)
        if message.sender != request.user:
            return JsonResponse({'status': 'error', 'message': 'You can only upload attachments to your own messages'})

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if file.size > max_size:
            return JsonResponse({'status': 'error', 'message': 'File too large (max 10MB)'})

        # Validate file type
        allowed_types = [
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'application/pdf', 'text/plain', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-excel',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'application/zip', 'application/x-rar-compressed'
        ]
        if file.content_type not in allowed_types:
            return JsonResponse({'status': 'error', 'message': 'File type not allowed'})

        # Create attachment
        attachment = Attachment.objects.create(
            message=message,
            file=file,
            file_name=file.name,
            mime_type=file.content_type,
            file_size=file.size
        )

        return JsonResponse({
            'status': 'success',
            'attachment': {
                'id': attachment.attachment_id,
                'file_name': attachment.file_name,
                'file_url': attachment.file.url,
                'file_size': attachment.file_size,
                'mime_type': attachment.mime_type
            }
        })

    except Message.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Message not found'})
    except Exception as e:
        logger.error(f"Error uploading attachment: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Upload failed'})

def get_client_ip(request):
    """Get the client IP address from the request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def get_user_conversations(user):
    """Get all conversations for a user (private and group)."""
    # Get private chats where user is user1 or user2
    private_conversations = Conversation.objects.filter(
        privatechat__user1=user
    ) | Conversation.objects.filter(
        privatechat__user2=user
    )

    # Get group chats where user is a member
    group_conversations = Conversation.objects.filter(
        groupchat__groupmember__user=user
    )

    # Combine the querysets using union (distinct is implicit in union)
    return private_conversations.union(group_conversations)
