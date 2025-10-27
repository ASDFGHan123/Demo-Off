from django import template

register = template.Library()

@register.filter
def has_perm(user, perm):
    """
    Check if a user has a specific permission.
    Usage: {% if user|has_perm:'app_label.permission_codename' %}
    """
    if not user.is_authenticated:
        return False
    return user.has_perm(perm)