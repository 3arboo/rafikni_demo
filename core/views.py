from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth.decorators import login_required 
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from .models import (
    User, Profile, Service, ServiceCategory, 
    ConsultationSlot, Consultation, Document,
    Notification, Review, Advertisement, FAQ,
    ConsultationRequest, Consultant, Booking
)
from .forms import (
    UserRegistrationForm, UserLoginForm,
    ProfileForm, ServiceForm, ConsultationSlotForm,
    DocumentForm, ReviewForm, ConsultationRequestForm  ,ConsultantForm
)
from django.utils.text import slugify
import uuid
from django.contrib.auth import login, logout, authenticate
from django.http import JsonResponse
from django.db.models.functions import Coalesce
from django.db import transaction
from datetime import timedelta
# ---- المصادقة والملف الشخصي ---- #
def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = user.email  # حتى لو ما تستخدم username
            user.save()

            Profile.objects.get_or_create(user=user)  # إنشاء البروفايل

            authenticated_user = authenticate(
                request,
                username=user.email,
                password=form.cleaned_data['password1']
                )

            if authenticated_user is not None:
                login(request, authenticated_user)
                messages.success(request, 'تم تسجيل الحساب بنجاح!')
                return redirect('dashboard')
            else:
                messages.error(request, 'حدث خطأ في المصادقة التلقائية. يرجى تسجيل الدخول يدويًا.')
                return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserRegistrationForm()

    return render(request, 'auth/register.html', {'form': form})

def user_login(request):
    if request.method == 'POST':
        # التعديل هنا: إزالة وسيط request
        form = UserLoginForm(request.POST)  # كان: form = UserLoginForm(request, data=request.POST)

        if form.is_valid():
            user = form.cleaned_data['user']

            # تذكرني functionality
            if not form.cleaned_data['remember_me']:
                request.session.set_expiry(0)  # تنتهي الجلسة عند إغلاق المتصفح

            login(request, user)

            # التحقق من تفعيل الحساب
            if not user.is_active:
                messages.error(request, 'حسابك غير مفعل. يرجى التواصل مع الدعم الفني.')
                return redirect('login')

            # التوجيه حسب الدور
            if user.role == User.Role.PROVIDER:
                messages.success(request, f'مرحباً بعودتك، {user.full_name}!')
                return redirect('provider_dashboard')
            else:
                messages.success(request, f'مرحباً بعودتك، {user.full_name}!')
                return redirect('client_dashboard')
        else:
            # عرض أخطاء محددة
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = UserLoginForm()

    return render(request, 'auth/login.html', {'form': form})

@login_required
def profile(request):
    profile = request.user.profile
    return render(request, 'profile/view.html', {'profile': profile})

@login_required
def switch_role(request):
    if request.method == 'POST':
        request.user.switch_role()
        messages.success(request, f'تم التبديل إلى {request.user.get_role_display()}')
    return redirect('dashboard')

@login_required
def edit_profile(request):
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الملف الشخصي بنجاح!')
            return redirect('profile')
    else:
        form = ProfileForm(instance=profile)

    return render(request, 'profile/edit.html', {'form': form})

# ---- لوحة التحكم ---- #
@login_required
def provider_dashboard(request):
    if request.user.role == User.Role.PROVIDER:
        # استعلامات لمقدم الخدمة
        services = Service.objects.filter(provider=request.user)
        bookings = Booking.objects.filter(service__provider=request.user)
        consultations = Consultation.objects.filter(slot__provider=request.user)
        
        # الإحصائيات
        context = {
            'active_services': services.filter(is_active=True).count(),
            'pending_consultations': consultations.filter(status='pending').count(),
            'completed_bookings': bookings.filter(status='completed').count(),
            'upcoming_appointments': consultations.filter(
                slot__start_time__gte=timezone.now(),
                status='confirmed'
            ).order_by('slot__start_time')[:5],
            'recent_reviews': Review.objects.filter(
                service__provider=request.user
            ).order_by('-created_at')[:3],
            'total_earnings': sum(booking.service.price for booking in bookings.filter(status='completed')),
            'active_ads': Advertisement.get_active_ads()
        }
        return render(request, 'dashboard/provider.html', context)
    else:
        return client_dashboard(request)

def calculate_percentage(numerator, denominator):
    """Safe percentage calculation with division by zero protection"""
    if denominator == 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)

@login_required
def client_dashboard(request):
    # استعلامات البيانات الأساسية
    consultations = Consultation.objects.filter(
        client=request.user
    ).select_related('slot')
    
    bookings = Booking.objects.filter(
        client=request.user
    ).select_related('slot', 'service')
    
    documents = Document.objects.filter(user=request.user)
    
    # الإحصائيات
    context = {
        'active_consultations': consultations.filter(
            status__in=['pending', 'confirmed']
        ).count(),
        'active_bookings': bookings.filter(
            status__in=['pending', 'confirmed'],
            slot__start_time__gte=timezone.now()
        ).count(),
        'documents_count': documents.count(),
        'unread_notifications': Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count(),
        'upcoming_consultations': consultations.filter(
            slot__start_time__gte=timezone.now(),
            status='confirmed'
        ).order_by('slot__start_time')[:3],
        'upcoming_bookings': bookings.filter(
            slot__start_time__gte=timezone.now(),
            status='confirmed'
        ).order_by('slot__start_time')[:3],
        'important_documents': get_important_documents(documents),
        'recent_notifications': Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:5],
        'active_ads': get_active_ads()
    }
    return render(request, 'dashboard/client.html', context)
        


@login_required
def dashboard(request):
    if request.user.role == User.Role.PROVIDER:
        return provider_dashboard(request)
    else:
      
        return client_dashboard(request)
    
def get_important_documents(documents):
    """معالجة آمنة للوثائق المهمة"""
    important_docs = []
    for doc in documents.filter(
        is_important=True,
        reminder_date__isnull=False
    ).order_by('reminder_date')[:3]:
        try:
            doc.reminder_days = (doc.reminder_date - timezone.now().date()).days
            doc.is_urgent = doc.reminder_days <= 3
            important_docs.append(doc)
        except Exception:
            continue
    return important_docs

def get_active_ads(limit=3):
    """الحصول على الإعلانات النشطة"""
    from .models import Advertisement
    return Advertisement.objects.filter(
        is_active=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).order_by('?')[:limit]



@login_required
def provider_profile(request):
    if request.user.role != User.Role.PROVIDER:
        messages.error(request, 'هذه الصفحة لمقدمي الخدمات فقط')
        return redirect('dashboard')
    
    consultant = get_object_or_404(Consultant, user=request.user)
    services = Service.objects.filter(provider=request.user)
    
    return render(request, 'profile/provider_profile.html', {
        'consultant': consultant,
        'services': services
    })

# ---- إدارة الخدمات ---- #
@login_required
def service_list(request):
    services = Service.objects.filter(provider=request.user)
    return render(request, 'services/list.html', {'services': services})

@login_required
def create_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = request.user
            
            # إنشاء slug فريد
            if not service.slug:
                base_slug = slugify(service.title)
                service.slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            
            service.save()
            messages.success(request, 'تم إنشاء الخدمة بنجاح!')
            return redirect('service_list')
    else:
        form = ServiceForm()
    
    return render(request, 'services/create.html', {'form': form})

@login_required
def update_service(request, pk):
    service = get_object_or_404(Service, pk=pk, provider=request.user)
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, 'تم تحديث الخدمة بنجاح!')
            return redirect('service_list')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'services/update.html', {'form': form})

# ---- إدارة المواعيد ---- #
@login_required
def slot_list(request):
    slots = ConsultationSlot.objects.filter(
        provider=request.user,
        start_time__gte=timezone.now()
    ).order_by('start_time')
    return render(request, 'consultations/slots.html', {'slots': slots})

@login_required
def create_slot(request):
    if request.method == 'POST':
        form = ConsultationSlotForm(request.POST, user=request.user)
        if form.is_valid():
            slot = form.save(commit=False)
            slot.provider = request.user
            slot.save()
            
            # هنا يمكنك معالجة المواعيد المتكررة إذا كان is_recurring True
            if form.cleaned_data.get('is_recurring'):
                # قم بتنفيذ منطق إنشاء مواعيد متكررة هنا
                pass
            
            messages.success(request, 'تم إضافة الموعد بنجاح!')
            return redirect('slot_list')
    else:
        form = ConsultationSlotForm(user=request.user)
    
    return render(request, 'consultations/create_slot.html', {'form': form})

# ---- البحث والاكتشاف ---- #
def browse_consultants(request):
    category_id = request.GET.get('category')
    query = request.GET.get('q')
    
    consultants = Consultant.objects.filter(available=True).select_related('user__profile')
    
    if category_id:
        consultants = consultants.filter(categories__id=category_id)
    
    if query:
        consultants = consultants.filter(
            Q(user__full_name__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(categories__name__icontains=query)
        ).distinct()
    
    categories = ServiceCategory.objects.annotate(
        consultant_count=Count('consultant')
    ).order_by('-consultant_count')
    
    paginator = Paginator(consultants, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    active_ads = Advertisement.objects.filter(
        is_active=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).order_by('?')[:2]
    
    return render(request, 'consultants/list.html', {
        'consultants': page_obj,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
        'search_query': query or '',
        'active_ads': active_ads
    })


@require_POST
@login_required
def book_consultation(request, slot_id):
    try:
        # الحصول على الموعد المطلوب
        slot = get_object_or_404(ConsultationSlot, id=slot_id, is_booked=False)
        
        # التحقق من أن المستخدم ليس هو مقدم الخدمة
        if slot.provider == request.user:
            messages.error(request, 'لا يمكنك حجز موعد مع نفسك')
            return redirect('consultant_detail', pk=slot.provider.consultant.pk)
        
        # التحقق من أن الموعد لم ينته بعد
        if slot.start_time < timezone.now():
            messages.error(request, 'هذا الموعد قد انتهى')
            return redirect('consultant_detail', pk=slot.provider.consultant.pk)
        
        # حجز الموعد
        slot.is_booked = True
        slot.save()
        
        # إنشاء استشارة جديدة
        consultation = Consultation.objects.create(
            client=request.user,
            consultant=slot.provider.consultant,
            slot=slot,
            status='pending',
            question="تم الحجز عبر الموقع"  # يمكن تغيير هذا النص
        )
        
        messages.success(request, 'تم حجز الموعد بنجاح! سيتواصل معك المستشار قريباً.')
        return redirect('consultation_detail', pk=consultation.id)
    
    except Exception as e:
        messages.error(request, f'حدث خطأ أثناء الحجز: {str(e)}')
        return redirect('home')


def consultant_detail(request, pk):
    consultant = get_object_or_404(Consultant, pk=pk, available=True)
    services = Service.objects.filter(provider=consultant.user, is_active=True)
    reviews = Review.objects.filter(service__provider=consultant.user).order_by('-created_at')
    
    # تحديد التاريخ المختار
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    try:
        selected_date = timezone.datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        selected_date = timezone.now().date()
    
    # الحصول على المواعيد المتاحة للتاريخ المحدد
    available_slots = ConsultationSlot.objects.filter(
        provider=consultant.user,
        is_booked=False,
        start_time__date=selected_date,
        start_time__gte=timezone.now()
    ).order_by('start_time')
    
    # حساب متوسط التقييم
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # حساب عدد التقييمات
    reviews_count = reviews.count()
    
    # معالجة تقييم المستخدم
    user_review = None
    if request.user.is_authenticated:
        user_review = reviews.filter(reviewer=request.user).first()
    
    if request.method == 'POST' and 'review' in request.POST:
        if not request.user.is_authenticated:
            messages.warning(request, 'يجب تسجيل الدخول لإضافة تقييم.')
            return redirect('login')
        
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.service = services.first()
            review.reviewer = request.user
            review.save()
            messages.success(request, 'شكراً لتقييمك هذا المستشار!')
            return redirect('consultant_detail', pk=pk)
    else:
        form = ReviewForm(instance=user_review)
    
    # توليد تواريخ الأسبوع
    week_dates = [selected_date + timedelta(days=i) for i in range(-3, 4)]
    
    # إضافة سمات خاصة بالمستشار للسياق
    consultant.average_rating = round(avg_rating, 1)
    consultant.reviews_count = reviews_count
    
    # الإعلانات النشطة
    active_ads = Advertisement.objects.filter(
        is_active=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).order_by('?')[:1]
    
    return render(request, 'consultants/detail.html', {
        'consultant': consultant,
        'services': services,
        'reviews': reviews,
        'available_slots': available_slots,
        'avg_rating': round(avg_rating, 1),
        'user_review': user_review,
        'form': form,
        'active_ads': active_ads,
        'week_dates': week_dates,
        'selected_date': selected_date
    })

# ---- إدارة الوثائق ---- #
@login_required
def document_list(request):
    documents = Document.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'documents/list.html', {'documents': documents})

@login_required
def upload_document(request):
    if request.method == 'POST':
        form = DocumentForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.user = request.user
            document.save()
            messages.success(request, 'تم رفع الوثيقة بنجاح!')
            return redirect('document_list')
    else:
        form = DocumentForm()
    return render(request, 'documents/upload.html', {'form': form})

@login_required
def delete_document(request, pk):
    document = get_object_or_404(Document, pk=pk, user=request.user)
    if request.method == 'POST':
        document.file.delete()
        document.delete()
        messages.success(request, 'تم حذف الوثيقة بنجاح!')
    return redirect('document_list')

# ---- نظام الاستشارات ---- #
@login_required
def request_consultation(request, consultant_id):
    consultant = get_object_or_404(Consultant, id=consultant_id)
    
    if request.method == 'POST':
        form = ConsultationRequestForm(request.POST)
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.client = request.user
            consultation.consultant = consultant.user
            consultation.save()
            
            # إرسال إشعار للمستشار
            Notification.objects.create(
                user=consultant.user,
                message=f"لديك طلب استشارة جديد من {request.user.full_name}",
                link=f"/consultations/{consultation.id}/"
            )
            
            messages.success(request, 'تم إرسال طلب الاستشارة بنجاح!')
            return redirect('consultation_list')
    else:
        form = ConsultationRequestForm(initial={'consultant': consultant.user})
    
    return render(request, 'consultations/request.html', {
        'form': form,
        'consultant': consultant
    })

@login_required
def book_consultation(request, slot_id):
    slot = get_object_or_404(ConsultationSlot, id=slot_id, is_booked=False)
    
    # إذا كان الموعد غير متاح (محجوز مسبقًا) أو انتهى وقته
    if slot.start_time <= timezone.now():
        messages.error(request, 'عذرًا، هذا الموعد لم يعد متاحًا.')
        return redirect('consultant_detail', pk=slot.provider.consultant.id)
    
    # تأكد أن المستخدم الحالي ليس هو مقدم الخدمة
    if slot.provider == request.user:
        messages.error(request, 'لا يمكنك حجز موعد خاص بك.')
        return redirect('consultant_detail', pk=slot.provider.consultant.id)
    
    # إنشاء استشارة جديدة
    consultation = Consultation.objects.create(
        slot=slot,
        client=request.user,
        status=Consultation.Status.CONFIRMED
    )
    
    # تحديث حالة الموعد ليكون محجوزًا
    slot.is_booked = True
    slot.save()
    
    # إرسال إشعار للمستشار
    Notification.objects.create(
        user=slot.provider,
        message=f"تم حجز موعد جديد من قبل {request.user.full_name}",
        link=f"/consultations/{consultation.id}/"
    )
    
    messages.success(request, 'تم حجز الموعد بنجاح!')
    return redirect('consultation_detail', pk=consultation.id)

# ---- نظام الإشعارات ---- #
@login_required
def notifications(request):
    if request.method == 'GET':
        # تحديث حالة القراءة عند زيارة الصفحة
        Notification.objects.filter(
            user=request.user, 
            is_read=False
        ).update(is_read=True)

    # معالجة طلبات تعليم الكل كمقروء أو حذف الكل
    if 'mark_all' in request.GET:
        Notification.objects.filter(user=request.user).update(is_read=True)
        messages.success(request, 'تم تعليم جميع الإشعارات كمقروءة')
        return redirect('notifications')
    
    if 'delete_all' in request.GET:
        Notification.objects.filter(user=request.user).delete()
        messages.success(request, 'تم حذف جميع الإشعارات')
        return redirect('notifications')
    
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'notifications/list.html', {
        'notifications': notifications
    })

# ---- الأسئلة الشائعة ---- #
def faq_list(request):
    featured_faqs = FAQ.objects.filter(is_featured=True).order_by('question')
    other_faqs = FAQ.objects.filter(is_featured=False).order_by('question')
    
    # الحصول على الإعلانات النشطة
    active_ads = Advertisement.objects.filter(
        is_active=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).order_by('?')[:2]  # 2 إعلانات عشوائية
    
    return render(request, 'faq/list.html', {
        'featured_faqs': featured_faqs,
        'other_faqs': other_faqs,
        'active_ads': active_ads
    })

def home(request):
    # الحصول على الإعلانات النشطة للصفحة الرئيسية
    featured_ads = Advertisement.objects.filter(
        is_active=True,
        #is_featured=True,
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).order_by('-created_at')[:3]
    
    featured_consultants = Consultant.objects.filter(
        available=True,
       # is_featured=True
    ).order_by('?')[:4]  # 4 مستشارين مميزين
    
    return render(request, 'home.html', {
        'featured_ads': featured_ads,
        'featured_consultants': featured_consultants
    })

def custom_logout(request):
    logout(request)
    messages.success(request, 'تم تسجيل الخروج بنجاح')
    return redirect('home')

def handler404(request, exception):
    return render(request, "404.html", status=404)

def autocomplete_consultants(request):
    query = request.GET.get('term', '')
    consultants = Consultant.objects.filter(
        Q(user__full_name__icontains=query) |
        Q(categories__name__icontains=query),
        available=True
    ).distinct()[:10]
    
    results = []
    for consultant in consultants:
        results.append({
            'id': consultant.id,
            'label': consultant.user.full_name,
            'value': consultant.user.full_name,
            'url': f"/consultant/{consultant.id}/"
        })
    return JsonResponse(results, safe=False)

@login_required
def consultation_list(request):
    status = request.GET.get('status', 'all')
    
    if request.user.role == User.Role.CLIENT:
        consultations = ConsultationRequest.objects.filter(client=request.user)
    else:
        consultations = ConsultationRequest.objects.filter(consultant=request.user)
    
    if status != 'all':
        consultations = consultations.filter(status=status)
    
    consultations = consultations.order_by('-created_at')
    
    return render(request, 'consultations/list.html', {
        'consultations': consultations,
        'status': status
    })

@login_required
def consultation_detail(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk)
    
    # التحقق من أن المستخدم له صلاحية رؤية الاستشارة
    if request.user != consultation.client and request.user != consultation.consultant.user:
        messages.error(request, 'ليس لديك صلاحية لعرض هذه الاستشارة')
        return redirect('home')
    
    # معالجة رد المستشار
    if request.method == 'POST' and 'response' in request.POST and request.user == consultation.consultant.user:
        consultation.response = request.POST.get('response')
        consultation.status = 'completed'
        consultation.save()
        messages.success(request, 'تم إرسال الرد بنجاح!')
        return redirect('consultation_detail', pk=pk)
    
    return render(request, 'consultations/detail.html', {
        'consultation': consultation
    })

@login_required
def respond_to_consultation(request, pk):
    consultation = get_object_or_404(ConsultationRequest, pk=pk, consultant=request.user)
    
    if request.method == 'POST':
        response = request.POST.get('response')
        status = request.POST.get('status')
        
        consultation.response = response
        consultation.status = status
        consultation.save()
        
        Notification.objects.create(
            user=consultation.client,
            message=f"تم الرد على استشارتك من قبل {request.user.full_name}",
            link=f"/consultations/{consultation.id}/"
        )
        
        messages.success(request, 'تم حفظ الرد بنجاح!')
        return redirect('consultation_detail', pk=pk)
    
    return render(request, 'consultations/respond.html', {
        'consultation': consultation
    })

@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(client=request.user).order_by('-created_at')
    
    # تصفية الحجوزات حسب الحالة
    status = request.GET.get('status')
    if status in ['pending', 'confirmed', 'completed', 'cancelled']:
        bookings = bookings.filter(status=status)
    
    # الترقيم
    paginator = Paginator(bookings, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'bookings/list.html', {
        'bookings': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages()
    })

@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(Booking, pk=pk, client=request.user)
    return render(request, 'bookings/detail.html', {'booking': booking})

@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, client=request.user)
    
    if request.method == 'POST':
        booking.status = 'cancelled'
        booking.cancel_reason = request.POST.get('cancel_reason', '')
        booking.save()
        
        # إرسال إشعار لمقدم الخدمة
        Notification.objects.create(
            user=booking.service.provider,
            message=f"تم إلغاء حجز من قبل {request.user.full_name}",
            link=f"/provider/bookings/{booking.id}/"
        )
        
        messages.success(request, 'تم إلغاء الحجز بنجاح')
        return redirect('my_bookings')
    
    return render(request, 'bookings/cancel_confirm.html', {'booking': booking})

@login_required
def available_slots(request):
    slots = ConsultationSlot.objects.filter(is_booked=False, start__gte=timezone.now()).order_by('start')
    return render(request, 'consultations/available_slots.html', {'slots': slots})

@login_required
def book_slot(request, slot_id):
    # منع مزوّد الخدمة من حجز الـ slot الخاص به
    slot = get_object_or_404(ConsultationSlot, pk=slot_id)
    if slot.provider_id == request.user.id:
        messages.error(request, 'لا يمكنك حجز موعد قدمته أنت كمزوّد خدمة.')
        return redirect('available_slots')

    # استخدم معاملة لقفل الصف وتجنّب السباق (race condition)
    try:
        with transaction.atomic():
            locked_slot = (ConsultationSlot.objects
                           .select_for_update()
                           .get(pk=slot_id))
            if locked_slot.is_booked:
                messages.error(request, 'تم حجز هذا الموعد بالفعل.')
                return redirect('available_slots')

            # أنشئ الحجز
            Booking.objects.create(slot=locked_slot, client=request.user)
            locked_slot.is_booked = True
            locked_slot.save()

        messages.success(request, 'تم حجز الموعد بنجاح!')
        return redirect('my_bookings')  # أو أي صفحة تريد
    except ConsultationSlot.DoesNotExist:
        messages.error(request, 'الموعد غير موجود.')
        return redirect('available_slots')


@login_required
def edit_consultant(request):
    consultant = get_object_or_404(Consultant, user=request.user)
    
    if request.method == 'POST':
        form = ConsultantForm(request.POST, request.FILES, instance=consultant, request=request)
        if form.is_valid():
            form.save()
            return redirect('provider_profile')
    else:
        # تحميل بيانات أوقات العمل من الجلسة إذا كانت موجودة
        initial_data = request.session.get('consultant_working_hours', {})
        form = ConsultantForm(instance=consultant, initial=initial_data, request=request)
    
    return render(request, 'consultants/edit.html', {'form': form})

@require_POST
@login_required
def cancel_consultation(request, pk):
    consultation = get_object_or_404(Consultation, pk=pk, client=request.user, status='pending')
    
    # تحرير الموعد
    if consultation.slot:
        consultation.slot.is_booked = False
        consultation.slot.save()
    
    # إلغاء الاستشارة
    consultation.status = 'cancelled'
    consultation.save()
    
    messages.success(request, 'تم إلغاء الاستشارة بنجاح')
    return redirect('client_dashboard')