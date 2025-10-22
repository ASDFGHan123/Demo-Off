from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.core.validators import MinLengthValidator
import uuid

class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username must be set')
        if not email:
            raise ValueError('The Email must be set')

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        return self.create_user(username, email, password, **extra_fields)

class User(AbstractBaseUser):
    user_id = models.AutoField(primary_key=True)
    username = models.CharField(max_length=50, unique=True, validators=[MinLengthValidator(3)])
    email = models.EmailField(unique=True, blank=True, null=True)
    password_hash = models.CharField(max_length=128)  # Will be handled by AbstractBaseUser
    display_name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    profile_image_url = models.URLField(blank=True, null=True)
    enable_notifications = models.BooleanField(default=True)
    notification_sound = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['display_name']

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        """Check if user has a specific permission."""
        if self.is_superuser:
            return True

        # Check permissions through roles
        user_permissions = set()
        for user_role in self.userrole_set.all():
            for role_perm in user_role.role.rolepermission_set.all():
                user_permissions.add(role_perm.permission.code)

        return perm in user_permissions

    def has_perms(self, perm_list, obj=None):
        """Check if user has a list of permissions."""
        if self.is_superuser:
            return True

        # Check permissions through roles
        user_permissions = set()
        for user_role in self.userrole_set.all():
            for role_perm in user_role.role.rolepermission_set.all():
                user_permissions.add(role_perm.permission.code)

        return all(perm in user_permissions for perm in perm_list)

    def has_module_perms(self, app_label):
        """Check if user has permissions for a specific app."""
        return self.is_superuser

    def get_user_permissions(self):
        """Get all permissions for this user."""
        if self.is_superuser:
            return Permission.objects.all()

        permissions = set()
        for user_role in self.userrole_set.all():
            for role_perm in user_role.role.rolepermission_set.all():
                permissions.add(role_perm.permission)

        return list(permissions)

    def get_user_roles(self):
        """Get all roles for this user."""
        return [ur.role for ur in self.userrole_set.all()]

    def has_role(self, role_name):
        """Check if user has a specific role."""
        return self.userrole_set.filter(role__name=role_name).exists()

    def can_access_conversation(self, conversation):
        """Check if user can access a conversation."""
        if not self.has_perm('view_chat'):
            return False

        if conversation.type == 'private':
            private_chat = conversation.privatechat
            return private_chat.user1 == self or private_chat.user2 == self
        elif conversation.type == 'group':
            return conversation.groupchat.groupmember_set.filter(user=self).exists()

        return False

    def can_send_message(self, conversation):
        """Check if user can send messages in a conversation."""
        return self.has_perm('send_message') and self.can_access_conversation(conversation)

    def can_edit_message(self, message):
        """Check if user can edit a message."""
        if message.sender == self and self.has_perm('edit_own_message'):
            return True
        if self.has_perm('edit_any_message') and self.can_access_conversation(message.conversation):
            return True
        return False

    def can_delete_message(self, message):
        """Check if user can delete a message."""
        if message.sender == self and self.has_perm('delete_own_message'):
            return True
        if self.has_perm('delete_any_message') and self.can_access_conversation(message.conversation):
            return True
        return False

    def can_manage_group(self, group_chat):
        """Check if user can manage a group chat."""
        if not self.can_access_conversation(group_chat.conversation):
            return False

        member = group_chat.groupmember_set.filter(user=self).first()
        if not member:
            return False

        # Group creator has admin privileges
        if group_chat.created_by == self:
            return True

        # Check role-based permissions
        if member.role == 'admin':
            return True

        return self.has_perm('manage_group_members') or self.has_perm('manage_group_settings')

    def can_kick_member(self, group_chat, target_user):
        """Check if user can kick a member from group."""
        if not self.can_manage_group(group_chat):
            return False

        if target_user == group_chat.created_by:
            return False  # Cannot kick group creator

        target_member = group_chat.groupmember_set.filter(user=target_user).first()
        if not target_member:
            return False

        # Admins can kick moderators and members, moderators can only kick members
        user_member = group_chat.groupmember_set.filter(user=self).first()
        if user_member.role == 'admin':
            return target_member.role in ['moderator', 'member']
        elif user_member.role == 'moderator':
            return target_member.role == 'member'

        return self.has_perm('kick_members')

    def can_ban_member(self, group_chat, target_user):
        """Check if user can ban a member from group."""
        return self.has_perm('ban_members') and self.can_manage_group(group_chat)

    def is_group_admin(self, group_chat):
        """Check if user is admin of the group."""
        member = group_chat.groupmember_set.filter(user=self).first()
        return member and (member.role == 'admin' or group_chat.created_by == self)

class Permission(models.Model):
    permission_id = models.AutoField(primary_key=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField()

    class Meta:
        db_table = 'permission'

    def __str__(self):
        return self.code

class Role(models.Model):
    role_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    permissions = models.ManyToManyField(Permission, through='RolePermission')

    class Meta:
        db_table = 'role'

    def __str__(self):
        return self.name

class RolePermission(models.Model):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column='role_id')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, db_column='permission_id')

    class Meta:
        db_table = 'role_permission'
        unique_together = ('role', 'permission')

    def __str__(self):
        return f"{self.role.name} - {self.permission.code}"

class UserRole(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, db_column='role_id')
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_role'
        unique_together = ('user', 'role')

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"

class Conversation(models.Model):
    CONVERSATION_TYPES = [
        ('private', 'Private Chat'),
        ('group', 'Group Chat'),
    ]

    conversation_id = models.AutoField(primary_key=True)
    type = models.CharField(max_length=10, choices=CONVERSATION_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200, blank=True, null=True)
    last_message = models.ForeignKey('Message', on_delete=models.SET_NULL, null=True, blank=True, related_name='last_message_conversations')

    class Meta:
        db_table = 'conversation'

    def __str__(self):
        return f"Conversation {self.conversation_id} ({self.type})"

class PrivateChat(models.Model):
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, primary_key=True, db_column='conversation_id')
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_chats_as_user1', db_column='user1_id')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='private_chats_as_user2', db_column='user2_id')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'private_chat'
        unique_together = ('user1', 'user2')

    def __str__(self):
        return f"Private chat: {self.user1.username} & {self.user2.username}"

    def get_participants(self):
        return [self.user1, self.user2]

class GroupChat(models.Model):
    conversation = models.OneToOneField(Conversation, on_delete=models.CASCADE, primary_key=True, db_column='conversation_id')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, db_column='created_by')
    description = models.TextField(blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_chat'

    def __str__(self):
        return f"Group: {self.conversation.title}"

class GroupMember(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('moderator', 'Moderator'),
        ('member', 'Member'),
    ]

    group_chat = models.ForeignKey(GroupChat, on_delete=models.CASCADE, db_column='group_chat_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'group_member'
        unique_together = ('group_chat', 'user')

    def __str__(self):
        return f"{self.user.username} in {self.group_chat}"

class Message(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('image', 'Image'),
        ('file', 'File'),
        ('system', 'System'),
    ]

    message_id = models.AutoField(primary_key=True)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, db_column='conversation_id')
    sender = models.ForeignKey(User, on_delete=models.CASCADE, db_column='sender_id')
    type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    content = models.TextField()
    sent_at = models.DateTimeField(auto_now_add=True)
    reply_to = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, db_column='reply_to_id')
    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'message'
        ordering = ['sent_at']

    def __str__(self):
        return f"Message {self.message_id} from {self.sender.username}"

class Attachment(models.Model):
    attachment_id = models.AutoField(primary_key=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, db_column='message_id')
    file = models.FileField(upload_to='attachments/', blank=True, null=True)
    file_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    file_size = models.IntegerField()  # Size in bytes
    thumbnail_url = models.URLField(blank=True, null=True)

    class Meta:
        db_table = 'attachment'

    def __str__(self):
        return self.file_name

class MessageStatus(models.Model):
    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('read', 'Read'),
    ]

    message = models.ForeignKey(Message, on_delete=models.CASCADE, db_column='message_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'message_status'
        unique_together = ('message', 'user')

    def __str__(self):
        return f"{self.message.message_id} - {self.user.username}: {self.status}"

class Reaction(models.Model):
    reaction_id = models.AutoField(primary_key=True)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, db_column='message_id')
    user = models.ForeignKey(User, on_delete=models.CASCADE, db_column='user_id')
    emoji = models.CharField(max_length=10)  # e.g., '👍', '❤️'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'reaction'
        unique_together = ('message', 'user', 'emoji')  # Prevent duplicate reactions from same user on same message

    def __str__(self):
        return f"{self.user.username} reacted {self.emoji} to message {self.message.message_id}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    ]

    TARGET_TYPES = [
        ('user', 'User'),
        ('message', 'Message'),
        ('conversation', 'Conversation'),
        ('group', 'Group'),
    ]

    log_id = models.AutoField(primary_key=True)
    actor = models.ForeignKey(User, on_delete=models.CASCADE, db_column='actor_id')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=20, choices=TARGET_TYPES)
    target_id = models.IntegerField()
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField()

    class Meta:
        db_table = 'audit_log'
        ordering = ['-timestamp']

    def __str__(self):
        return f"Audit {self.log_id}: {self.actor.username} {self.action} {self.target_type}"
