from django.contrib import admin
from .models import (
    User, Permission, Role, RolePermission, UserRole,
    Conversation, PrivateChat, GroupChat, GroupMember,
    Message, Attachment, MessageStatus, Reaction, AuditLog
)

# Inline classes
class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0

class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0

class GroupMemberInline(admin.TabularInline):
    model = GroupMember
    extra = 0

class AttachmentInline(admin.TabularInline):
    model = Attachment
    extra = 0

class MessageStatusInline(admin.TabularInline):
    model = MessageStatus
    extra = 0

class ReactionInline(admin.TabularInline):
    model = Reaction
    extra = 0

class PrivateChatInline(admin.StackedInline):
    model = PrivateChat
    can_delete = False
    verbose_name_plural = 'Private Chat Details'

class GroupChatInline(admin.StackedInline):
    model = GroupChat
    can_delete = False
    verbose_name_plural = 'Group Chat Details'

# Admin classes
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'display_name', 'is_active', 'is_staff', 'is_superuser', 'created_at', 'last_seen')
    search_fields = ('username', 'email', 'display_name')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'created_at', 'last_seen')
    inlines = [UserRoleInline]

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('code', 'description')
    search_fields = ('code', 'description')
    list_filter = ()

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    list_filter = ()
    inlines = [RolePermissionInline, UserRoleInline]

@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission')
    search_fields = ('role__name', 'permission__code')
    list_filter = ('role', 'permission')

@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'assigned_at')
    search_fields = ('user__username', 'role__name')
    list_filter = ('role', 'assigned_at')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('conversation_id', 'type', 'title', 'created_at', 'last_message')
    search_fields = ('title', 'type')
    list_filter = ('type', 'created_at')
    inlines = [PrivateChatInline, GroupChatInline]

@admin.register(PrivateChat)
class PrivateChatAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'user1', 'user2', 'created_at')
    search_fields = ('user1__username', 'user2__username')
    list_filter = ('created_at',)

@admin.register(GroupChat)
class GroupChatAdmin(admin.ModelAdmin):
    list_display = ('conversation', 'created_by', 'description', 'created_at')
    search_fields = ('conversation__title', 'created_by__username', 'description')
    list_filter = ('created_at',)
    inlines = [GroupMemberInline]

@admin.register(GroupMember)
class GroupMemberAdmin(admin.ModelAdmin):
    list_display = ('group_chat', 'user', 'role', 'joined_at')
    search_fields = ('group_chat__conversation__title', 'user__username', 'role')
    list_filter = ('role', 'joined_at')

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('message_id', 'conversation', 'sender', 'type', 'content', 'sent_at', 'is_edited', 'is_deleted')
    search_fields = ('sender__username', 'content', 'conversation__title')
    list_filter = ('type', 'sent_at', 'is_edited', 'is_deleted')
    inlines = [AttachmentInline, MessageStatusInline, ReactionInline]

@admin.register(Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    list_display = ('attachment_id', 'message', 'file_name', 'mime_type', 'file_size')
    search_fields = ('file_name', 'mime_type')
    list_filter = ('mime_type',)

@admin.register(MessageStatus)
class MessageStatusAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'status', 'updated_at')
    search_fields = ('message__message_id', 'user__username', 'status')
    list_filter = ('status', 'updated_at')

@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ('reaction_id', 'message', 'user', 'emoji', 'created_at')
    search_fields = ('message__message_id', 'user__username', 'emoji')
    list_filter = ('emoji', 'created_at')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'actor', 'action', 'target_type', 'target_id', 'timestamp', 'ip_address')
    search_fields = ('actor__username', 'action', 'target_type', 'ip_address')
    list_filter = ('action', 'target_type', 'timestamp')
