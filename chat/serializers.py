from rest_framework import serializers
from .models import User, Conversation, Message, Attachment, PrivateChat, GroupChat, GroupMember, Reaction
import re

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['user_id', 'username', 'email', 'display_name', 'created_at', 'is_online', 'last_seen', 'profile_image_url']
        read_only_fields = ['user_id', 'created_at', 'last_seen']

class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ['conversation_id', 'type', 'created_at', 'title', 'last_message']
        read_only_fields = ['conversation_id', 'created_at']

class MessageSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['message_id', 'conversation', 'sender', 'type', 'content', 'sent_at', 'reply_to', 'is_edited', 'is_deleted', 'edited_at', 'deleted_at', 'reactions']
        read_only_fields = ['message_id', 'sent_at', 'edited_at', 'deleted_at']

    def validate_content(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("Message content cannot be empty")
        if len(value) > 1000:
            raise serializers.ValidationError("Message content cannot exceed 1000 characters")
        return value.strip()

    def create(self, validated_data):
        validated_data['sender'] = self.context['request'].user
        return super().create(validated_data)

    def get_reactions(self, obj):
        reactions = Reaction.objects.filter(message=obj)
        return ReactionSerializer(reactions, many=True).data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make conversation read-only when creating via URL (conversation is set from URL)
        if hasattr(self, 'context') and 'request' in self.context:
            request = self.context['request']
            if request.method == 'POST' and 'conversation_id' in self.context.get('view', {}).kwargs:
                self.fields['conversation'].read_only = True

class AttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attachment
        fields = ['attachment_id', 'message', 'file', 'file_name', 'mime_type', 'file_size', 'thumbnail_url']
        read_only_fields = ['attachment_id']

class ReactionSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)

    class Meta:
        model = Reaction
        fields = ['reaction_id', 'message', 'user', 'emoji', 'created_at']
        read_only_fields = ['reaction_id', 'created_at']

class MessageSearchSerializer(serializers.ModelSerializer):
    sender = UserSerializer(read_only=True)
    conversation_title = serializers.SerializerMethodField()
    highlighted_content = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ['message_id', 'conversation', 'conversation_title', 'sender', 'type', 'content', 'highlighted_content', 'sent_at', 'reply_to', 'is_edited', 'is_deleted', 'edited_at', 'deleted_at', 'reactions']
        read_only_fields = ['message_id', 'sent_at', 'edited_at', 'deleted_at']

    def get_conversation_title(self, obj):
        if obj.conversation.type == 'private':
            # Get the other user in the private chat
            private_chat = obj.conversation.privatechat
            user = self.context['request'].user
            other_user = private_chat.user2 if private_chat.user1 == user else private_chat.user1
            return f"Chat with {other_user.display_name}"
        else:
            return obj.conversation.title or "Group Chat"

    def get_highlighted_content(self, obj):
        query = self.context.get('search_query', '')
        if not query:
            return obj.content

        # Simple highlighting - wrap matches with <mark> tags
        highlighted = re.sub(
            f'({re.escape(query)})',
            r'<mark>\1</mark>',
            obj.content,
            flags=re.IGNORECASE
        )
        return highlighted

    def get_reactions(self, obj):
        reactions = Reaction.objects.filter(message=obj)
        return ReactionSerializer(reactions, many=True).data