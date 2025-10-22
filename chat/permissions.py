from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from .models import User


def permission_required(permission_code):
    """
    Decorator to check if user has a specific permission.
    Redirects to 403 page if permission denied.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not request.user.has_perm(permission_code):
                return HttpResponseForbidden("You don't have permission to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def permissions_required(permission_codes):
    """
    Decorator to check if user has all specified permissions.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not request.user.has_perms(permission_codes):
                return HttpResponseForbidden("You don't have permission to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def role_required(role_name):
    """
    Decorator to check if user has a specific role.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if not request.user.has_role(role_name):
                return HttpResponseForbidden("You don't have the required role to access this resource.")

            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def conversation_access_required(view_func):
    """
    Decorator to check if user can access a conversation.
    Expects 'conversation_id' in URL kwargs.
    """
    @wraps(view_func)
    def _wrapped_view(request, conversation_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        from .models import Conversation
        try:
            conversation = Conversation.objects.get(pk=conversation_id)
            if not request.user.can_access_conversation(conversation):
                return HttpResponseForbidden("You don't have access to this conversation.")
        except Conversation.DoesNotExist:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound("Conversation not found.")

        return view_func(request, conversation_id, *args, **kwargs)
    return _wrapped_view


def group_admin_required(view_func):
    """
    Decorator to check if user is admin of a group.
    Expects 'conversation_id' in URL kwargs and conversation must be a group chat.
    """
    @wraps(view_func)
    def _wrapped_view(request, conversation_id, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        from .models import Conversation
        try:
            conversation = Conversation.objects.get(pk=conversation_id)
            if conversation.type != 'group':
                return HttpResponseForbidden("This operation is only available for group chats.")

            if not request.user.is_group_admin(conversation.groupchat):
                return HttpResponseForbidden("You must be a group admin to perform this action.")

        except Conversation.DoesNotExist:
            from django.http import HttpResponseNotFound
            return HttpResponseNotFound("Conversation not found.")

        return view_func(request, conversation_id, *args, **kwargs)
    return _wrapped_view


class PermissionMixin:
    """
    Mixin class for class-based views to handle permissions.
    """

    required_permissions = []
    required_role = None
    require_authentication = True

    def dispatch(self, request, *args, **kwargs):
        if self.require_authentication and not request.user.is_authenticated:
            return redirect('login')

        if self.required_permissions:
            if isinstance(self.required_permissions, str):
                permissions = [self.required_permissions]
            else:
                permissions = self.required_permissions

            if not request.user.has_perms(permissions):
                return HttpResponseForbidden("You don't have the required permissions.")

        if self.required_role and not request.user.has_role(self.required_role):
            return HttpResponseForbidden("You don't have the required role.")

        return super().dispatch(request, *args, **kwargs)


class ConversationAccessMixin(PermissionMixin):
    """
    Mixin to ensure user has access to a conversation.
    Expects 'conversation_id' in URL kwargs.
    """

    def dispatch(self, request, *args, **kwargs):
        conversation_id = kwargs.get('conversation_id')
        if conversation_id:
            from .models import Conversation
            try:
                conversation = Conversation.objects.get(pk=conversation_id)
                if not request.user.can_access_conversation(conversation):
                    return HttpResponseForbidden("You don't have access to this conversation.")
            except Conversation.DoesNotExist:
                from django.http import HttpResponseNotFound
                return HttpResponseNotFound("Conversation not found.")

        return super().dispatch(request, *args, **kwargs)


class GroupAdminMixin(ConversationAccessMixin):
    """
    Mixin to ensure user is admin of a group chat.
    """

    def dispatch(self, request, *args, **kwargs):
        conversation_id = kwargs.get('conversation_id')
        if conversation_id:
            from .models import Conversation
            try:
                conversation = Conversation.objects.get(pk=conversation_id)
                if conversation.type != 'group':
                    return HttpResponseForbidden("This operation is only available for group chats.")

                if not request.user.is_group_admin(conversation.groupchat):
                    return HttpResponseForbidden("You must be a group admin to perform this action.")

            except Conversation.DoesNotExist:
                from django.http import HttpResponseNotFound
                return HttpResponseNotFound("Conversation not found.")

        return super().dispatch(request, *args, **kwargs)