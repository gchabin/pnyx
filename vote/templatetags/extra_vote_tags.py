from django import template

register = template.Library()

@register.filter
def keyvalue(dict, key):
    """Get the value of a dictionary dynamically """
    return dict.get(key, None)