from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.db import models
from django.db.models import Q
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import logging
from .models import User, Conversation, Message, Attachment, PrivateChat, GroupChat, GroupMember
from .serializers import UserSerializer, ConversationSerializer, MessageSerializer, AttachmentSerializer, MessageSearchSerializer

# Set up logging
logger = logging.getLogger(__name__)

# User API Views
class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing users for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve users'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class UserDetailView(generics.RetrieveUpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error retrieving user details for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve user details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error updating user details for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to update user details'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Conversation API Views
class ConversationListView(generics.ListCreateAPIView):
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            from .views import get_user_conversations
            return get_user_conversations(self.request.user)
        except Exception as e:
            logger.error(f"Error getting conversations for user {self.request.user.username}: {str(e)}")
            return Conversation.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing conversations for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve conversations'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        # This will be handled by specific create views for private/group chats
        pass

class ConversationDetailView(generics.RetrieveAPIView):
    queryset = Conversation.objects.all()
    serializer_class = ConversationSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'conversation_id'

    def retrieve(self, request, *args, **kwargs):
        try:
            conversation = self.get_object()
            # Check if user has access to this conversation
            user = request.user
            if not user.can_access_conversation(conversation):
                logger.warning(f"User {user.username} attempted to access unauthorized conversation {conversation.conversation_id}")
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

            return super().retrieve(request, *args, **kwargs)
        except Conversation.DoesNotExist:
            logger.warning(f"User {request.user.username} attempted to access non-existent conversation {kwargs.get('conversation_id')}")
            return Response({'error': 'Conversation not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving conversation for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve conversation'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Message API Views
class MessageListView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination

    def get_queryset(self):
        try:
            conversation_id = self.kwargs['conversation_id']
            conversation = Conversation.objects.get(conversation_id=conversation_id)

            # Check if user has access to this conversation
            user = self.request.user
            if not user.can_access_conversation(conversation):
                return Message.objects.none()

            # Optimized query with select_related and prefetch_related
            return Message.objects.filter(
                conversation_id=conversation_id,
                is_deleted=False
            ).select_related(
                'sender',
                'reply_to',
                'reply_to__sender'
            ).prefetch_related(
                'reaction_set',
                'attachment_set'
            ).order_by('sent_at')
        except Conversation.DoesNotExist:
            logger.warning(f"User {self.request.user.username} attempted to access messages from non-existent conversation {self.kwargs.get('conversation_id')}")
            return Message.objects.none()
        except Exception as e:
            logger.error(f"Error getting messages for conversation {self.kwargs.get('conversation_id')}: {str(e)}")
            return Message.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            # Add pagination for large chat histories
            page = self.paginate_queryset(self.get_queryset())
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(self.get_queryset(), many=True)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing messages for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve messages'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        try:
            conversation_id = self.kwargs['conversation_id']
            conversation = get_object_or_404(Conversation, conversation_id=conversation_id)

            # Check if user has access to this conversation
            user = self.request.user
            if not user.can_access_conversation(conversation):
                raise PermissionError("Access denied")

            serializer.save(conversation=conversation)
        except Conversation.DoesNotExist:
            logger.warning(f"User {self.request.user.username} attempted to create message in non-existent conversation {conversation_id}")
            raise
        except PermissionError:
            logger.warning(f"User {self.request.user.username} attempted to create message in unauthorized conversation {conversation_id}")
            raise
        except Exception as e:
            logger.error(f"Error creating message for user {self.request.user.username}: {str(e)}")
            raise

class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'message_id'

    def get_queryset(self):
        return Message.objects.filter(sender=self.request.user)

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error retrieving message for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve message'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error updating message for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to update message'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error deleting message for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to delete message'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Attachment API Views
class AttachmentListView(generics.ListCreateAPIView):
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        try:
            message_id = self.kwargs.get('message_id')
            if message_id:
                # Check if user has access to the message
                message = Message.objects.filter(message_id=message_id).first()
                if message and not self.request.user.can_access_conversation(message.conversation):
                    return Attachment.objects.none()
                return Attachment.objects.filter(message_id=message_id)
            return Attachment.objects.filter(message__sender=self.request.user)
        except Exception as e:
            logger.error(f"Error getting attachments for user {self.request.user.username}: {str(e)}")
            return Attachment.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error listing attachments for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve attachments'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def perform_create(self, serializer):
        try:
            message_id = self.kwargs.get('message_id')
            if message_id:
                message = get_object_or_404(Message, message_id=message_id, sender=self.request.user)
                serializer.save(message=message)
        except Message.DoesNotExist:
            logger.warning(f"User {self.request.user.username} attempted to create attachment for non-existent message {message_id}")
            raise
        except Exception as e:
            logger.error(f"Error creating attachment for user {self.request.user.username}: {str(e)}")
            raise

class AttachmentDetailView(generics.RetrieveAPIView):
    queryset = Attachment.objects.all()
    serializer_class = AttachmentSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'attachment_id'

    def retrieve(self, request, *args, **kwargs):
        try:
            attachment = self.get_object()
            # Check if user has access to the attachment's message
            message = attachment.message
            user = request.user
            if not user.can_access_conversation(message.conversation):
                logger.warning(f"User {user.username} attempted to access unauthorized attachment {attachment.attachment_id}")
                return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

            return super().retrieve(request, *args, **kwargs)
        except Attachment.DoesNotExist:
            logger.warning(f"User {request.user.username} attempted to access non-existent attachment {kwargs.get('attachment_id')}")
            return Response({'error': 'Attachment not found'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error retrieving attachment for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to retrieve attachment'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class MessageSearchPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class MessageSearchView(generics.ListAPIView):
    serializer_class = MessageSearchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = MessageSearchPagination

    def get_queryset(self):
        try:
            query = self.request.query_params.get('q', '').strip()
            if not query:
                return Message.objects.none()

            user = self.request.user

            # Get conversations the user has access to
            from .views import get_user_conversations
            accessible_conversations = get_user_conversations(user)

            # Filter messages by accessible conversations and search query
            # Using PostgreSQL full-text search if available, otherwise fallback to icontains
            try:
                search_vector = SearchVector('content')
                search_query = SearchQuery(query)
                messages = Message.objects.filter(
                    conversation__in=accessible_conversations
                ).annotate(
                    search_rank=SearchRank(search_vector, search_query)
                ).filter(
                    search_vector=search_query
                ).order_by('-search_rank', '-sent_at')
            except:
                # Fallback for databases without full-text search
                messages = Message.objects.filter(
                    conversation__in=accessible_conversations,
                    content__icontains=query
                ).order_by('-sent_at')

            return messages
        except Exception as e:
            logger.error(f"Error searching messages for user {self.request.user.username}: {str(e)}")
            return Message.objects.none()

    def list(self, request, *args, **kwargs):
        try:
            queryset = self.get_queryset()
            page = self.paginate_queryset(queryset)
            if page is not None:
                serializer = self.get_serializer(page, many=True, context={'request': request, 'search_query': request.query_params.get('q', '')})
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(queryset, many=True, context={'request': request, 'search_query': request.query_params.get('q', '')})
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error listing search results for {request.user.username}: {str(e)}")
            return Response({'error': 'Failed to search messages'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Additional API Views for specific operations
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_private_chat(request):
    try:
        other_user_id = request.data.get('user_id')
        if not other_user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            other_user = User.objects.get(user_id=other_user_id)
        except User.DoesNotExist:
            logger.warning(f"User {request.user.username} attempted to create chat with non-existent user {other_user_id}")
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if other_user == request.user:
            return Response({'error': 'Cannot create chat with yourself'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if private chat already exists
        existing_chat = PrivateChat.objects.filter(
            (models.Q(user1=request.user) & models.Q(user2=other_user)) |
            (models.Q(user1=other_user) & models.Q(user2=request.user))
        ).first()

        if existing_chat:
            serializer = ConversationSerializer(existing_chat.conversation)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Create new conversation and private chat
        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=request.user, user2=other_user)

        serializer = ConversationSerializer(conversation)
        logger.info(f"User {request.user.username} created private chat with {other_user.username}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating private chat for user {request.user.username}: {str(e)}")
        return Response({'error': 'Failed to create private chat'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([])  # Allow unauthenticated access for registration
@method_decorator(csrf_exempt, name='dispatch')
def register_user(request):
    try:
        username = request.data.get('username')
        email = request.data.get('email')
        password = request.data.get('password')
        display_name = request.data.get('display_name')

        if not username or not password or not display_name:
            return Response({'error': 'Username, password, and display name are required'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for existing username
        if User.objects.filter(username=username).exists():
            return Response({'error': 'Username taken'}, status=status.HTTP_400_BAD_REQUEST)

        # Check for existing email only if email is provided
        if email and User.objects.filter(email=email).exists():
            return Response({'error': 'Email already registered'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.create_user(username=username, email=email if email else None, password=password, display_name=display_name)
            # Log the user in
            from django.contrib.auth import login
            login(request, user)
            serializer = UserSerializer(user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f"Registration error: {str(e)}")
            return Response({'error': 'Registration failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Error registering user: {str(e)}")
        return Response({'error': 'Failed to register user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_group_chat(request):
    try:
        title = request.data.get('title')
        description = request.data.get('description', '')
        member_ids = request.data.get('member_ids', [])

        if not title:
            return Response({'error': 'Title is required'}, status=status.HTTP_400_BAD_REQUEST)

        if len(title) > 100:
            return Response({'error': 'Title must be 100 characters or less'}, status=status.HTTP_400_BAD_REQUEST)

        if not member_ids:
            return Response({'error': 'At least one member is required'}, status=status.HTTP_400_BAD_REQUEST)

        if len(member_ids) > 50:
            return Response({'error': 'Group cannot have more than 50 members'}, status=status.HTTP_400_BAD_REQUEST)

        # Create conversation
        conversation = Conversation.objects.create(type='group', title=title)

        # Create group chat
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=request.user, description=description)

        # Add creator as admin
        GroupMember.objects.create(group_chat=group_chat, user=request.user, role='admin')

        # Add selected members
        added_members = 0
        for user_id in member_ids:
            try:
                user = User.objects.get(user_id=user_id)
                GroupMember.objects.create(group_chat=group_chat, user=user, role='member')
                added_members += 1
            except User.DoesNotExist:
                logger.warning(f"User {user_id} not found when creating group chat")
                continue

        serializer = ConversationSerializer(conversation)
        logger.info(f"User {request.user.username} created group chat '{title}' with {added_members} members")
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    except Exception as e:
        logger.error(f"Error creating group chat for user {request.user.username}: {str(e)}")
        return Response({'error': 'Failed to create group chat'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)