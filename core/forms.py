from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import (
    User, Profile, Service, ConsultationSlot,
    Document, Review, ConsultationRequest , Service , Consultation
)
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import  authenticate

class UserRegistrationForm(UserCreationForm):
    full_name = forms.CharField(
        label='الاسم الكامل',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text='أدخل اسمك الكامل (الاسم الأول واسم العائلة)'
    )
    
    email = forms.EmailField(
        label='البريد الإلكتروني',
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text='سيتم استخدامه لتسجيل الدخول'
    )
    
    phone = forms.CharField(
        label='رقم الهاتف',
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        required=False
    )
    
    role = forms.ChoiceField(
        label='نوع الحساب',
        choices=User.Role.choices,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        initial=User.Role.CLIENT
    )
    
    class Meta:
        model = User
        fields = ['full_name', 'email', 'phone', 'role', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # إزالة حقول username التي لم تعد موجودة
        if 'username' in self.fields:
            del self.fields['username']
        
        # تخصيص رسائل المساعدة
        self.fields['password1'].help_text = 'يجب أن تحتوي على 8 أحرف على الأقل'
        self.fields['password2'].help_text = 'أعد إدخال كلمة المرور للتأكيد'
        self.fields['password1'].widget.attrs.update({
        'class': 'form-control',
       'placeholder': 'كلمة المرور'
       })
        self.fields['password2'].widget.attrs.update({
    'class': 'form-control',
    'placeholder': 'كلمة المرور'
        })

        
class UserLoginForm(forms.Form):
    email = forms.EmailField(
        label='البريد الإلكتروني',
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'example@example.com',
            'autofocus': True
        })
    )
    password = forms.CharField(
        label='كلمة المرور',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'كلمة المرور'
        })
    )
    remember_me = forms.BooleanField(
        label='تذكرني',
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        if email and password:
            # المصادقة باستخدام البريد الإلكتروني
            user = authenticate(email=email, password=password)
            
            if user is None:
                raise forms.ValidationError(
                    'البريد الإلكتروني أو كلمة المرور غير صحيحة'
                )
            elif not user.is_active:
                raise forms.ValidationError(
                    'حسابك غير مفعل. يرجى التواصل مع الدعم الفني.'
                )
            
            cleaned_data['user'] = user
        return cleaned_data
    
class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('profile_image', 'bio', 'address', 'website')
        labels = {
            'profile_image': _('صورة الملف الشخصي'),
            'bio': _('نبذة عنك'),
            'address': _('العنوان'),
            'website': _('الموقع الإلكتروني'),
        }
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ('title', 'category', 'description', 'price', 'duration', 'is_active')
        labels = {
            'title': _('عنوان الخدمة'),
            'category': _('التصنيف'),
            'description': _('وصف الخدمة'),
            'price': _('السعر'),
            'duration': _('المدة المقدرة'),
            'is_active': _('نشط'),
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'duration': forms.TextInput(attrs={'placeholder': 'HH:MM:SS'}),
        }

from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .models import ConsultationSlot

class ConsultationSlotForm(forms.ModelForm):
    class Meta:
        model = ConsultationSlot
        fields = ('start_time', 'end_time', 'is_recurring')
        labels = {
            'start_time': _('وقت البدء'),
            'end_time': _('وقت الانتهاء'),
        }
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # استخراج user من kwargs
        super().__init__(*args, **kwargs)
        
        # يمكنك إضافة أي تعديلات على الحقول هنا بناءً على المستخدم
        if self.user:
            self.fields['start_time'].widget.attrs['min'] = timezone.now().strftime('%Y-%m-%dT%H:%M')
    
    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        
        if start_time and end_time:
            if start_time >= end_time:
                raise forms.ValidationError(_('وقت الانتهاء يجب أن يكون بعد وقت البدء'))
            if start_time < timezone.now():
                raise forms.ValidationError(_('لا يمكن تحديد موعد في الماضي'))
            
            # تحقق إضافي إذا كان المستخدم متوفراً
            if self.user:
                overlapping_slots = ConsultationSlot.objects.filter(
                    provider=self.user,
                    start_time__lt=end_time,
                    end_time__gt=start_time
                )
                if overlapping_slots.exists():
                    raise forms.ValidationError(_('هذا الموعد يتعارض مع مواعيد أخرى لديك'))
        
        return cleaned_data

class DocumentForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ('title', 'file', 'description', 'reminder_date', 'is_important')
        labels = {
            'title': _('عنوان الوثيقة'),
            'file': _('الملف'),
            'description': _('وصف الوثيقة'),
            'reminder_date': _('تاريخ التذكير'),
            'is_important': _('مهم'),
        }
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'reminder_date': forms.DateInput(attrs={'type': 'date'}),
        }

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ('rating', 'comment')
        labels = {
            'rating': _('التقييم'),
            'comment': _('التعليق'),
        }
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': _('شاركنا تجربتك مع هذه الخدمة...')}),
        }

class ConsultationRequestForm(forms.ModelForm):
    # أضف حقل الخدمة كحقل اختيار
    service = forms.ModelChoiceField(
        queryset=Service.objects.none(),  # سنحدده في الدالة __init__
        label=_('الخدمة'),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )
    
    class Meta:
        model = ConsultationRequest
        fields = ('service', 'question')
        labels = {
            'question': _('سؤالك أو استفسارك'),
        }
        widgets = {
            'question': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': _('صف مشكلتك أو استفسارك بالتفصيل...'),
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # تحديث queryset ليشمل فقط الخدمات النشطة
        self.fields['service'].queryset = Service.objects.filter(is_active=True)


class BookSlotForm(forms.ModelForm):
    class Meta:
        model = Consultation
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'أي ملاحظات أو تفاصيل إضافية تريد مشاركتها مع المستشار'
            })
        }