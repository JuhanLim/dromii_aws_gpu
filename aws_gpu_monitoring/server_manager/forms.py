from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .models import Reservation, Instance

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    회원가입 폼
    """
    email = forms.EmailField(
        label=_('이메일'),
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': '이메일 주소'})
    )
    username = forms.CharField(
        label=_('사용자 이름'),
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '사용자 이름'})
    )
    password1 = forms.CharField(
        label=_('비밀번호'),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '비밀번호'})
    )
    password2 = forms.CharField(
        label=_('비밀번호 확인'),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '비밀번호 확인'})
    )
    
    class Meta:
        model = User
        fields = ('email', 'username', 'password1', 'password2')


class CustomAuthenticationForm(AuthenticationForm):
    """
    로그인 폼
    """
    username = forms.EmailField(
        label=_('이메일'),
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': '이메일 주소'})
    )
    password = forms.CharField(
        label=_('비밀번호'),
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': '비밀번호'})
    )


class ReservationForm(forms.ModelForm):
    """
    인스턴스 예약 폼
    """
    start_time = forms.DateTimeField(
        label=_('시작 시간'),
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    end_time = forms.DateTimeField(
        label=_('종료 시간'),
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control',
            'type': 'datetime-local'
        })
    )
    purpose = forms.CharField(
        label=_('사용 목적'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '인스턴스를 사용하려는 목적을 간략히 적어주세요.'
        }),
        required=True
    )
    
    class Meta:
        model = Reservation
        fields = ('start_time', 'end_time', 'purpose')
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError(_('종료 시간은 시작 시간보다 이후여야 합니다.'))
            
            # 최대 예약 시간 제한 (예: 24시간)
            if (end_time - start_time).total_seconds() > 24 * 60 * 60:
                raise forms.ValidationError(_('최대 예약 시간은 24시간입니다.'))
        
        return cleaned_data


class ReservationAdminForm(forms.ModelForm):
    """
    관리자용 예약 관리 폼
    """
    STATUS_CHOICES = (
        ('pending', '대기중'),
        ('approved', '승인됨'),
        ('rejected', '거부됨'),
        ('canceled', '취소됨'),
        ('completed', '완료됨'),
    )
    
    status = forms.ChoiceField(
        label=_('상태'),
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    admin_comment = forms.CharField(
        label=_('관리자 코멘트'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': '예약에 대한 코멘트를 남겨주세요.'
        }),
        required=False
    )
    
    class Meta:
        model = Reservation
        fields = ('status', 'admin_comment')
