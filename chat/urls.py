from django.urls import path, include
from . import views, api_views
from rest_framework.routers import DefaultRouter
from django.http import JsonResponse

# CSRF token endpoint
def csrf_token_view(request):
    return JsonResponse({'csrfToken': request.META.get('CSRF_COOKIE', '')})

# API Router
router = DefaultRouter()

urlpatterns = [
    path('api/csrf/', csrf_token_view, name='csrf_token'),
    # Web views
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('chats/', views.chat_list, name='chat_list'),
    path('chats/create-private/', views.create_private_chat, name='create_private_chat'),
    path('chats/create-group/', views.create_group_chat, name='create_group_chat'),
    path('chat/<int:conversation_id>/', views.chat_detail, name='chat_detail'),
    path('chat/<int:conversation_id>/send/', views.SendMessageView.as_view(), name='send_message'),
    path('upload-attachment/', views.upload_attachment, name='upload_attachment'),
    path('search/', views.user_search, name='user_search'),

    # API views
    path('api/users/me/', api_views.UserDetailView.as_view(), name='api_auth_user'),
    path('api/auth/register/', api_views.register_user, name='api_register'),
    path('api/users/', api_views.UserListView.as_view(), name='api_user_list'),
    path('api/users/<int:user_id>/', api_views.UserDetailView.as_view(), name='api_user_detail'),
    path('api/conversations/', api_views.ConversationListView.as_view(), name='api_conversation_list'),
    path('api/conversations/<int:conversation_id>/', api_views.ConversationDetailView.as_view(), name='api_conversation_detail'),
    path('api/conversations/<int:conversation_id>/messages/', api_views.MessageListView.as_view(), name='api_message_list'),
    path('api/messages/<int:message_id>/', api_views.MessageDetailView.as_view(), name='api_message_detail'),
    path('api/attachments/', api_views.AttachmentListView.as_view(), name='api_attachment_list'),
    path('api/messages/<int:message_id>/attachments/', api_views.AttachmentListView.as_view(), name='api_message_attachment_list'),
    path('api/attachments/<int:attachment_id>/', api_views.AttachmentDetailView.as_view(), name='api_attachment_detail'),
    path('api/search/messages/', api_views.MessageSearchView.as_view(), name='api_message_search'),
    path('api/create-private-chat/', api_views.create_private_chat, name='api_create_private_chat'),
    path('api/create-group-chat/', api_views.create_group_chat, name='api_create_group_chat'),
]