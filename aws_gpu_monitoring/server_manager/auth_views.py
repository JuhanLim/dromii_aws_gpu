from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from .forms import CustomUserCreationForm, CustomAuthenticationForm


def register_view(request):
    """
    회원가입 뷰
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, _('회원가입이 완료되었습니다.'))
            return redirect('dashboard')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'server_manager/auth/register.html', {'form': form})


def login_view(request):
    """
    로그인 뷰
    """
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    if request.method == 'POST':
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, _('로그인이 완료되었습니다.'))
                return redirect('dashboard')
            else:
                messages.error(request, _('이메일 또는 비밀번호가 올바르지 않습니다.'))
    else:
        form = CustomAuthenticationForm()
    
    return render(request, 'server_manager/auth/login.html', {'form': form})


@login_required
def logout_view(request):
    """
    로그아웃 뷰
    """
    logout(request)
    messages.success(request, _('로그아웃되었습니다.'))
    return redirect('login')


@login_required
def profile_view(request):
    """
    사용자 프로필 뷰
    """
    return render(request, 'server_manager/auth/profile.html')
