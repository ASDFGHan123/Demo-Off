from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth import authenticate
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from channels.testing import WebsocketCommunicator
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async
import json
from unittest.mock import patch, MagicMock
from .models import (
    User, Permission, Role, RolePermission, UserRole, Conversation,
    Message, PrivateChat, GroupChat, GroupMember, Attachment,
    MessageStatus, Reaction, AuditLog
)
from .consumers import ChatConsumer
from .permissions import (
    permission_required, permissions_required, role_required,
    conversation_access_required, group_admin_required,
    PermissionMixin, ConversationAccessMixin, GroupAdminMixin
)
from .serializers import (
    UserSerializer, ConversationSerializer, MessageSerializer,
    AttachmentSerializer, ReactionSerializer, MessageSearchSerializer
)

# Model Unit Tests
class UserModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )

    def test_user_creation(self):
        """Test user creation with required fields"""
        self.assertEqual(self.user.username, 'testuser')
        self.assertEqual(self.user.email, 'test@example.com')
        self.assertEqual(self.user.display_name, 'Test User')
        self.assertTrue(self.user.check_password('testpass123'))

    def test_user_str(self):
        """Test user string representation"""
        self.assertEqual(str(self.user), 'testuser')

    def test_username_validation(self):
        """Test username minimum length validation"""
        with self.assertRaises(ValidationError):
            User.objects.create_user(
                username='ab',  # Too short
                email='test2@example.com',
                password='testpass123',
                display_name='Test User 2'
            )

    def test_unique_username_email(self):
        """Test unique constraints on username and email"""
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                username='testuser',  # Duplicate username
                email='test2@example.com',
                password='testpass123',
                display_name='Test User 2'
            )

    def test_superuser_creation(self):
        """Test superuser creation"""
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            display_name='Admin User'
        )
        self.assertTrue(superuser.is_superuser)
        self.assertTrue(superuser.is_staff)

    def test_has_perm_superuser(self):
        """Test superuser has all permissions"""
        superuser = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='adminpass123',
            display_name='Admin User'
        )
        self.assertTrue(superuser.has_perm('any_permission'))
        self.assertTrue(superuser.has_perms(['perm1', 'perm2']))

    def test_has_perm_with_roles(self):
        """Test permission checking through roles"""
        # Create permission and role
        perm = Permission.objects.create(code='test_perm', description='Test permission')
        role = Role.objects.create(name='test_role', description='Test role')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role)

        self.assertTrue(self.user.has_perm('test_perm'))
        self.assertTrue(self.user.has_perms(['test_perm']))
        self.assertFalse(self.user.has_perm('nonexistent_perm'))

    def test_has_role(self):
        """Test role checking"""
        role = Role.objects.create(name='test_role', description='Test role')
        UserRole.objects.create(user=self.user, role=role)

        self.assertTrue(self.user.has_role('test_role'))
        self.assertFalse(self.user.has_role('nonexistent_role'))

    def test_can_access_conversation_private(self):
        """Test private conversation access"""
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=self.user, user2=user2)

        self.assertTrue(self.user.can_access_conversation(conversation))
        self.assertTrue(user2.can_access_conversation(conversation))

        # Test unauthorized access
        user3 = User.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='testpass123',
            display_name='User 3'
        )
        self.assertFalse(user3.can_access_conversation(conversation))

    def test_can_access_conversation_group(self):
        """Test group conversation access"""
        conversation = Conversation.objects.create(type='group', title='Test Group')
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=self.user)
        GroupMember.objects.create(group_chat=group_chat, user=self.user, role='admin')

        self.assertTrue(self.user.can_access_conversation(conversation))

        # Test non-member access
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        self.assertFalse(user2.can_access_conversation(conversation))

    def test_can_send_message(self):
        """Test message sending permission"""
        # Create permission
        perm = Permission.objects.create(code='send_message', description='Can send messages')
        role = Role.objects.create(name='member', description='Member role')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role)

        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=self.user, user2=self.user)  # Self-chat for simplicity

        self.assertTrue(self.user.can_send_message(conversation))

    def test_can_edit_message(self):
        """Test message editing permissions"""
        # Create permissions
        edit_own = Permission.objects.create(code='edit_own_message', description='Can edit own messages')
        edit_any = Permission.objects.create(code='edit_any_message', description='Can edit any message')
        role = Role.objects.create(name='member', description='Member role')
        RolePermission.objects.create(role=role, permission=edit_own)
        UserRole.objects.create(user=self.user, role=role)

        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=self.user, user2=self.user)
        message = Message.objects.create(conversation=conversation, sender=self.user, content='Test')

        # Can edit own message
        self.assertTrue(self.user.can_edit_message(message))

        # Cannot edit others' messages without permission
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        message2 = Message.objects.create(conversation=conversation, sender=user2, content='Test')
        self.assertFalse(self.user.can_edit_message(message2))

        # Can edit any message with proper permission
        RolePermission.objects.create(role=role, permission=edit_any)
        self.assertTrue(self.user.can_edit_message(message2))

    def test_group_management_permissions(self):
        """Test group management permissions"""
        conversation = Conversation.objects.create(type='group', title='Test Group')
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=self.user)
        GroupMember.objects.create(group_chat=group_chat, user=self.user, role='admin')

        # Creator has admin privileges
        self.assertTrue(self.user.can_manage_group(group_chat))
        self.assertTrue(self.user.is_group_admin(group_chat))

        # Test member permissions
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        GroupMember.objects.create(group_chat=group_chat, user=user2, role='member')

        manage_perm = Permission.objects.create(code='manage_group_members', description='Can manage group members')
        role = Role.objects.create(name='moderator', description='Moderator role')
        RolePermission.objects.create(role=role, permission=manage_perm)
        UserRole.objects.create(user=user2, role=role)

        self.assertTrue(user2.can_manage_group(group_chat))

    def test_kick_member_permissions(self):
        """Test member kicking permissions"""
        conversation = Conversation.objects.create(type='group', title='Test Group')
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=self.user)
        GroupMember.objects.create(group_chat=group_chat, user=self.user, role='admin')

        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        GroupMember.objects.create(group_chat=group_chat, user=user2, role='moderator')

        user3 = User.objects.create_user(
            username='user3',
            email='user3@example.com',
            password='testpass123',
            display_name='User 3'
        )
        GroupMember.objects.create(group_chat=group_chat, user=user3, role='member')

        # Admin can kick moderator and member
        self.assertTrue(self.user.can_kick_member(group_chat, user2))
        self.assertTrue(self.user.can_kick_member(group_chat, user3))

        # Cannot kick group creator
        self.assertFalse(user2.can_kick_member(group_chat, self.user))

        # Moderator can kick member but not moderator
        self.assertTrue(user2.can_kick_member(group_chat, user3))
        self.assertFalse(user2.can_kick_member(group_chat, user2))


class PermissionModelTest(TestCase):
    def test_permission_creation(self):
        """Test permission creation"""
        perm = Permission.objects.create(code='test_perm', description='Test permission')
        self.assertEqual(str(perm), 'test_perm')


class RoleModelTest(TestCase):
    def test_role_creation(self):
        """Test role creation"""
        role = Role.objects.create(name='test_role', description='Test role')
        self.assertEqual(str(role), 'test_role')


class RolePermissionModelTest(TestCase):
    def test_role_permission_creation(self):
        """Test role-permission relationship"""
        perm = Permission.objects.create(code='test_perm', description='Test permission')
        role = Role.objects.create(name='test_role', description='Test role')
        role_perm = RolePermission.objects.create(role=role, permission=perm)
        self.assertEqual(str(role_perm), 'test_role - test_perm')

    def test_unique_constraint(self):
        """Test unique constraint on role-permission pairs"""
        perm = Permission.objects.create(code='test_perm', description='Test permission')
        role = Role.objects.create(name='test_role', description='Test role')
        RolePermission.objects.create(role=role, permission=perm)

        with self.assertRaises(IntegrityError):
            RolePermission.objects.create(role=role, permission=perm)


class UserRoleModelTest(TestCase):
    def test_user_role_creation(self):
        """Test user-role assignment"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        role = Role.objects.create(name='test_role', description='Test role')
        user_role = UserRole.objects.create(user=user, role=role)
        self.assertEqual(str(user_role), 'testuser - test_role')

    def test_unique_constraint(self):
        """Test unique constraint on user-role pairs"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        role = Role.objects.create(name='test_role', description='Test role')
        UserRole.objects.create(user=user, role=role)

        with self.assertRaises(IntegrityError):
            UserRole.objects.create(user=user, role=role)


class ConversationModelTest(TestCase):
    def test_conversation_creation(self):
        """Test conversation creation"""
        conv = Conversation.objects.create(type='private')
        self.assertEqual(str(conv), f"Conversation {conv.conversation_id} (private)")


class PrivateChatModelTest(TestCase):
    def test_private_chat_creation(self):
        """Test private chat creation"""
        user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        conversation = Conversation.objects.create(type='private')
        private_chat = PrivateChat.objects.create(conversation=conversation, user1=user1, user2=user2)

        self.assertEqual(str(private_chat), "Private chat: user1 & user2")
        self.assertEqual(private_chat.get_participants(), [user1, user2])

    def test_unique_constraint(self):
        """Test unique constraint on private chat pairs"""
        user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='testpass123',
            display_name='User 2'
        )
        conversation1 = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation1, user1=user1, user2=user2)

        conversation2 = Conversation.objects.create(type='private')
        with self.assertRaises(IntegrityError):
            PrivateChat.objects.create(conversation=conversation2, user1=user1, user2=user2)


class GroupChatModelTest(TestCase):
    def test_group_chat_creation(self):
        """Test group chat creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='group', title='Test Group')
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=user)

        self.assertEqual(str(group_chat), "Group: Test Group")


class GroupMemberModelTest(TestCase):
    def test_group_member_creation(self):
        """Test group member creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='group', title='Test Group')
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=user)
        member = GroupMember.objects.create(group_chat=group_chat, user=user, role='admin')

        self.assertEqual(str(member), "user1 in Group: Test Group")

    def test_unique_constraint(self):
        """Test unique constraint on group-user pairs"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='group', title='Test Group')
        group_chat = GroupChat.objects.create(conversation=conversation, created_by=user)
        GroupMember.objects.create(group_chat=group_chat, user=user, role='admin')

        with self.assertRaises(IntegrityError):
            GroupMember.objects.create(group_chat=group_chat, user=user, role='member')


class MessageModelTest(TestCase):
    def test_message_creation(self):
        """Test message creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=user, content='Test message')

        self.assertEqual(str(message), f"Message {message.message_id} from user1")
        self.assertEqual(message.type, 'text')

    def test_message_reply(self):
        """Test message reply functionality"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        original_message = Message.objects.create(conversation=conversation, sender=user, content='Original')
        reply_message = Message.objects.create(conversation=conversation, sender=user, content='Reply', reply_to=original_message)

        self.assertEqual(reply_message.reply_to, original_message)


class AttachmentModelTest(TestCase):
    def test_attachment_creation(self):
        """Test attachment creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=user, content='Test')
        attachment = Attachment.objects.create(
            message=message,
            file_name='test.txt',
            mime_type='text/plain',
            file_size=100
        )

        self.assertEqual(str(attachment), 'test.txt')


class MessageStatusModelTest(TestCase):
    def test_message_status_creation(self):
        """Test message status creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=user, content='Test')
        status = MessageStatus.objects.create(message=message, user=user, status='read')

        self.assertEqual(str(status), f"{message.message_id} - user1: read")

    def test_unique_constraint(self):
        """Test unique constraint on message-user status pairs"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=user, content='Test')
        MessageStatus.objects.create(message=message, user=user, status='read')

        with self.assertRaises(IntegrityError):
            MessageStatus.objects.create(message=message, user=user, status='delivered')


class ReactionModelTest(TestCase):
    def test_reaction_creation(self):
        """Test reaction creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=user, content='Test')
        reaction = Reaction.objects.create(message=message, user=user, emoji='👍')

        self.assertEqual(str(reaction), f"user1 reacted 👍 to message {message.message_id}")

    def test_unique_constraint(self):
        """Test unique constraint on message-user-emoji combinations"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=user, content='Test')
        Reaction.objects.create(message=message, user=user, emoji='👍')

        with self.assertRaises(IntegrityError):
            Reaction.objects.create(message=message, user=user, emoji='👍')


class AuditLogModelTest(TestCase):
    def test_audit_log_creation(self):
        """Test audit log creation"""
        user = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='testpass123',
            display_name='User 1'
        )
        log = AuditLog.objects.create(
            actor=user,
            action='create',
            target_type='user',
            target_id=1,
            ip_address='127.0.0.1'
        )

        self.assertEqual(str(log), f"Audit {log.log_id}: user1 create user")


# Permission Decorator Tests
class PermissionDecoratorTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        self.client = Client()

    def test_permission_required_decorator_success(self):
        """Test permission_required decorator with valid permission"""
        # Create permission and assign to user
        perm = Permission.objects.create(code='test_perm', description='Test permission')
        role = Role.objects.create(name='test_role', description='Test role')
        RolePermission.objects.create(role=role, permission=perm)
        UserRole.objects.create(user=self.user, role=role)

        @permission_required('test_perm')
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse('Success')

        # Mock request
        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.user
        request.method = 'GET'

        response = test_view(request)
        self.assertEqual(response.status, 200)

    def test_permission_required_decorator_failure(self):
        """Test permission_required decorator without permission"""
        @permission_required('nonexistent_perm')
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse('Success')

        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.user
        request.method = 'GET'

        response = test_view(request)
        self.assertEqual(response.status, 403)

    def test_permissions_required_decorator(self):
        """Test permissions_required decorator"""
        # Create permissions and assign to user
        perm1 = Permission.objects.create(code='perm1', description='Permission 1')
        perm2 = Permission.objects.create(code='perm2', description='Permission 2')
        role = Role.objects.create(name='test_role', description='Test role')
        RolePermission.objects.create(role=role, permission=perm1)
        RolePermission.objects.create(role=role, permission=perm2)
        UserRole.objects.create(user=self.user, role=role)

        @permissions_required(['perm1', 'perm2'])
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse('Success')

        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.user
        request.method = 'GET'

        response = test_view(request)
        self.assertEqual(response.status, 200)

    def test_role_required_decorator(self):
        """Test role_required decorator"""
        role = Role.objects.create(name='test_role', description='Test role')
        UserRole.objects.create(user=self.user, role=role)

        @role_required('test_role')
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse('Success')

        from django.http import HttpRequest
        request = HttpRequest()
        request.user = self.user
        request.method = 'GET'

        response = test_view(request)
        self.assertEqual(response.status, 200)


# Serializer Tests
class SerializerTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        self.conversation = Conversation.objects.create(type='private')
        self.message = Message.objects.create(
            conversation=self.conversation,
            sender=self.user,
            content='Test message'
        )

    def test_user_serializer(self):
        """Test User serializer"""
        serializer = UserSerializer(self.user)
        data = serializer.data
        self.assertEqual(data['username'], 'testuser')
        self.assertEqual(data['display_name'], 'Test User')

    def test_message_serializer_validation(self):
        """Test Message serializer validation"""
        # Valid message
        serializer = MessageSerializer(data={'content': 'Valid message'})
        self.assertTrue(serializer.is_valid())

        # Empty content
        serializer = MessageSerializer(data={'content': ''})
        self.assertFalse(serializer.is_valid())

        # Too long content
        long_content = 'x' * 1001
        serializer = MessageSerializer(data={'content': long_content})
        self.assertFalse(serializer.is_valid())

    def test_conversation_serializer(self):
        """Test Conversation serializer"""
        serializer = ConversationSerializer(self.conversation)
        data = serializer.data
        self.assertEqual(data['type'], 'private')

    def test_reaction_serializer(self):
        """Test Reaction serializer"""
        reaction = Reaction.objects.create(message=self.message, user=self.user, emoji='👍')
        serializer = ReactionSerializer(reaction)
        data = serializer.data
        self.assertEqual(data['emoji'], '👍')


# API Tests
class ChatAPITestCase(APITestCase):
    def setUp(self):
        # Create test users
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123',
            display_name='Test User 1'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            display_name='Test User 2'
        )
        self.user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123',
            display_name='Test User 3'
        )

        # Create permissions and roles for testing
        view_chat_perm = Permission.objects.create(code='view_chat', description='Can view chat')
        send_message_perm = Permission.objects.create(code='send_message', description='Can send messages')
        member_role = Role.objects.create(name='member', description='Member role')
        RolePermission.objects.create(role=member_role, permission=view_chat_perm)
        RolePermission.objects.create(role=member_role, permission=send_message_perm)
        UserRole.objects.create(user=self.user1, role=member_role)
        UserRole.objects.create(user=self.user2, role=member_role)

    def test_user_api_list(self):
        """Test that authenticated user can list users"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_user_api_detail(self):
        """Test that user can retrieve their own details"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/users/{self.user1.user_id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser1')

    def test_user_api_detail_unauthorized(self):
        """Test that user cannot access others' details"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get(f'/api/users/{self.user2.user_id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_conversation_list(self):
        """Test conversation listing"""
        self.client.force_authenticate(user=self.user1)
        response = self.client.get('/api/conversations/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_private_chat(self):
        """Test creating a private chat"""
        self.client.force_authenticate(user=self.user1)
        data = {'user_id': self.user2.user_id}
        response = self.client.post('/api/create-private-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('conversation_id', response.data)

    def test_create_private_chat_self(self):
        """Test creating a private chat with oneself fails"""
        self.client.force_authenticate(user=self.user1)
        data = {'user_id': self.user1.user_id}
        response = self.client.post('/api/create-private-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_private_chat_duplicate(self):
        """Test creating duplicate private chat returns existing"""
        self.client.force_authenticate(user=self.user1)
        data = {'user_id': self.user2.user_id}
        response1 = self.client.post('/api/create-private-chat/', data)
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        response2 = self.client.post('/api/create-private-chat/', data)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data['conversation_id'], response2.data['conversation_id'])

    def test_create_group_chat(self):
        """Test creating a group chat"""
        self.client.force_authenticate(user=self.user1)
        data = {
            'title': 'Test Group',
            'description': 'Test description',
            'member_ids': [self.user2.user_id]
        }
        response = self.client.post('/api/create-group-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('conversation_id', response.data)

    def test_create_group_chat_validation(self):
        """Test group chat creation validation"""
        self.client.force_authenticate(user=self.user1)

        # No title
        data = {'member_ids': [self.user2.user_id]}
        response = self.client.post('/api/create-group-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Title too long
        data = {'title': 'x' * 101, 'member_ids': [self.user2.user_id]}
        response = self.client.post('/api/create-group-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # No members
        data = {'title': 'Test Group'}
        response = self.client.post('/api/create-group-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Too many members
        member_ids = [i for i in range(51)]
        data = {'title': 'Test Group', 'member_ids': member_ids}
        response = self.client.post('/api/create-group-chat/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_message_operations(self):
        """Test message CRUD operations"""
        # Create a conversation first
        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=self.user1, user2=self.user2)

        self.client.force_authenticate(user=self.user1)

        # Create message
        data = {'content': 'Test message'}
        response = self.client.post(f'/api/conversations/{conversation.conversation_id}/messages/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        message_id = response.data['message_id']

        # List messages
        response = self.client.get(f'/api/conversations/{conversation.conversation_id}/messages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)

        # Update message
        update_data = {'content': 'Updated message'}
        response = self.client.patch(f'/api/messages/{message_id}/', update_data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Delete message
        response = self.client.delete(f'/api/messages/{message_id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_message_access_control(self):
        """Test message access control"""
        # Create conversation user1 is not part of
        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=self.user2, user2=self.user3)

        self.client.force_authenticate(user=self.user1)

        # Try to create message in unauthorized conversation
        data = {'content': 'Test message'}
        response = self.client.post(f'/api/conversations/{conversation.conversation_id}/messages/', data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_message_search(self):
        """Test message search functionality"""
        # Create conversation and messages
        conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=conversation, user1=self.user1, user2=self.user2)
        Message.objects.create(conversation=conversation, sender=self.user1, content='Hello world')
        Message.objects.create(conversation=conversation, sender=self.user2, content='Test message')

        self.client.force_authenticate(user=self.user1)

        # Search for messages
        response = self.client.get('/api/messages/search/?q=hello')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(len(response.data), 0)


# WebSocket Consumer Tests
class ChatConsumerTest(TransactionTestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123',
            display_name='Test User 1'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            display_name='Test User 2'
        )

        # Create permissions
        view_chat_perm = Permission.objects.create(code='view_chat', description='Can view chat')
        send_message_perm = Permission.objects.create(code='send_message', description='Can send messages')
        member_role = Role.objects.create(name='member', description='Member role')
        RolePermission.objects.create(role=member_role, permission=view_chat_perm)
        RolePermission.objects.create(role=member_role, permission=send_message_perm)
        UserRole.objects.create(user=self.user1, role=member_role)
        UserRole.objects.create(user=self.user2, role=member_role)

        # Create conversation
        self.conversation = Conversation.objects.create(type='private')
        PrivateChat.objects.create(conversation=self.conversation, user1=self.user1, user2=self.user2)

    async def test_connect_authenticated(self):
        """Test WebSocket connection with authenticated user"""
        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = self.user1
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def test_connect_unauthenticated(self):
        """Test WebSocket connection fails for unauthenticated user"""
        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = None  # Anonymous user
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_connect_unauthorized_conversation(self):
        """Test WebSocket connection fails for unauthorized conversation"""
        user3 = User.objects.create_user(
            username='testuser3',
            email='test3@example.com',
            password='testpass123',
            display_name='Test User 3'
        )
        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = user3
        connected, _ = await communicator.connect()
        self.assertFalse(connected)

    async def test_send_message(self):
        """Test sending messages via WebSocket"""
        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = self.user1
        await communicator.connect()

        # Send message
        message_data = {'message': 'Hello WebSocket!'}
        await communicator.send_json_to(message_data)

        # Receive response
        response = await communicator.receive_json_from()
        self.assertIn('message', response)
        self.assertEqual(response['message'], 'Hello WebSocket!')
        self.assertEqual(response['user'], 'testuser1')

        await communicator.disconnect()

    async def test_send_empty_message(self):
        """Test sending empty message fails"""
        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = self.user1
        await communicator.connect()

        # Send empty message
        message_data = {'message': ''}
        await communicator.send_json_to(message_data)

        # Receive error response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('empty', response['message'].lower())

        await communicator.disconnect()

    async def test_send_long_message(self):
        """Test sending message that's too long fails"""
        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = self.user1
        await communicator.connect()

        # Send very long message
        long_message = 'x' * 1001
        message_data = {'message': long_message}
        await communicator.send_json_to(message_data)

        # Receive error response
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'error')
        self.assertIn('long', response['message'].lower())

        await communicator.disconnect()

    async def test_reaction_functionality(self):
        """Test reaction functionality"""
        # Create a message first
        message = await sync_to_async(Message.objects.create)(
            conversation=self.conversation,
            sender=self.user1,
            content='Test message'
        )

        communicator = WebsocketCommunicator(ChatConsumer, f'/ws/chat/{self.conversation.conversation_id}/')
        communicator.scope['user'] = self.user1
        await communicator.connect()

        # Send reaction
        reaction_data = {'type': 'reaction', 'message_id': message.message_id, 'emoji': '👍'}
        await communicator.send_json_to(reaction_data)

        # Receive reaction update
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'reaction')
        self.assertEqual(response['message_id'], message.message_id)

        await communicator.disconnect()


# Integration Tests for Views
class ViewIntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            display_name='Test User'
        )
        self.client.login(username='testuser', password='testpass123')

        # Create permissions for admin panel
        view_admin_perm = Permission.objects.create(code='view_admin_panel', description='Can view admin panel')
        role = Role.objects.create(name='admin', description='Admin role')
        RolePermission.objects.create(role=role, permission=view_admin_perm)
        UserRole.objects.create(user=self.user, role=role)

    def test_admin_panel_access(self):
        """Test admin panel access"""
        response = self.client.get('/admin-panel/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('total_users', response.context)

    def test_admin_panel_no_permission(self):
        """Test admin panel access denied without permission"""
        # Remove permission
        UserRole.objects.filter(user=self.user).delete()
        response = self.client.get('/admin-panel/')
        self.assertEqual(response.status_code, 403)


# Edge Cases and Error Handling
class EdgeCaseTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username='testuser1',
            email='test1@example.com',
            password='testpass123',
            display_name='Test User 1'
        )
        self.user2 = User.objects.create_user(
            username='testuser2',
            email='test2@example.com',
            password='testpass123',
            display_name='Test User 2'
        )

    def test_conversation_without_participants(self):
        """Test conversation creation without proper participants"""
        conversation = Conversation.objects.create(type='private')
        # This should not be allowed in practice, but test the model handles it
        self.assertIsNotNone(conversation)

    def test_message_without_conversation(self):
        """Test message creation edge cases"""
        # This should fail due to foreign key constraint
        with self.assertRaises(Exception):
            Message.objects.create(sender=self.user1, content='Test')

    def test_group_chat_without_creator(self):
        """Test group chat creation edge cases"""
        conversation = Conversation.objects.create(type='group')
        # This should work but creator field is required
        with self.assertRaises(Exception):
            GroupChat.objects.create(conversation=conversation)

    def test_circular_message_reply(self):
        """Test circular reply references"""
        conversation = Conversation.objects.create(type='private')
        message1 = Message.objects.create(conversation=conversation, sender=self.user1, content='Message 1')
        message2 = Message.objects.create(conversation=conversation, sender=self.user2, content='Message 2', reply_to=message1)

        # Test that reply_to works
        self.assertEqual(message2.reply_to, message1)

    def test_user_online_status_toggle(self):
        """Test user online status changes"""
        self.assertFalse(self.user1.is_online)
        self.user1.is_online = True
        self.user1.save()
        self.user1.refresh_from_db()
        self.assertTrue(self.user1.is_online)

    def test_audit_log_ip_validation(self):
        """Test audit log IP address validation"""
        # Valid IP
        log = AuditLog.objects.create(
            actor=self.user1,
            action='login',
            target_type='user',
            target_id=self.user1.user_id,
            ip_address='192.168.1.1'
        )
        self.assertIsNotNone(log)

        # Invalid IP should raise validation error
        with self.assertRaises(Exception):
            AuditLog.objects.create(
                actor=self.user1,
                action='login',
                target_type='user',
                target_id=self.user1.user_id,
                ip_address='invalid-ip'
            )

    def test_message_status_transitions(self):
        """Test message status state transitions"""
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=self.user1, content='Test')

        # Create status progression
        status1 = MessageStatus.objects.create(message=message, user=self.user2, status='sent')
        self.assertEqual(status1.status, 'sent')

        # Update to delivered
        status1.status = 'delivered'
        status1.save()
        status1.refresh_from_db()
        self.assertEqual(status1.status, 'delivered')

        # Update to read
        status1.status = 'read'
        status1.save()
        status1.refresh_from_db()
        self.assertEqual(status1.status, 'read')

    def test_reaction_toggle(self):
        """Test reaction toggle functionality"""
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=self.user1, content='Test')

        # Add reaction
        reaction1 = Reaction.objects.create(message=message, user=self.user2, emoji='👍')
        self.assertIsNotNone(reaction1)

        # Try to add same reaction again (should fail due to unique constraint)
        with self.assertRaises(IntegrityError):
            Reaction.objects.create(message=message, user=self.user2, emoji='👍')

    def test_attachment_validation(self):
        """Test attachment validation"""
        conversation = Conversation.objects.create(type='private')
        message = Message.objects.create(conversation=conversation, sender=self.user1, content='Test')

        # Valid attachment
        attachment = Attachment.objects.create(
            message=message,
            file_name='test.txt',
            mime_type='text/plain',
            file_size=100
        )
        self.assertIsNotNone(attachment)

        # Test file size limits (assuming 10MB limit)
        large_attachment = Attachment.objects.create(
            message=message,
            file_name='large.txt',
            mime_type='text/plain',
            file_size=10 * 1024 * 1024  # 10MB
        )
        self.assertIsNotNone(large_attachment)
