from django import template

register = template.Library()

@register.filter
def div(value, arg):
    """
    나눗셈 연산을 위한 템플릿 필터
    사용법: {{ value|div:arg }}
    """
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def mul(value, arg):
    """
    곱셈 연산을 위한 템플릿 필터
    사용법: {{ value|mul:arg }}
    """
    try:
        return float(value) * float(arg)
    except ValueError:
        return 0