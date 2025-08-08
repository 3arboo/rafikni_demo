from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q, Count, Avg
from django.core.paginator import Paginator
from .models import (
    User, Profile, Service, ServiceCategory, 
    ConsultationSlot, Consultation, Document,
    Notification, Review, Advertisement, FAQ,
    ConsultationRequest , Consultant ,Booking
)
from .forms import (
    UserRegistrationForm, UserLoginForm,
    ProfileForm, ServiceForm, ConsultationSlotForm,
    DocumentForm, ReviewForm, ConsultationRequestForm 
)
from django.utils.text import slugify
import uuid
from django.contrib.auth import login , logout
# ---- المصادقة والملف الشخصي ---- #
from django.contrib.auth import login, authenticate

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # مصادقة المستخدم باستخدام البريد الإلكتروني وكلمة المرور
            authenticated_user = authenticate(
                request,
                email=form.cleaned_data['email'],
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
    form = ProfileForm(instance=profile)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect('profile')

    return render(request, 'profile/edit.html', {'form': form})

# ---- لوحة التحكم ---- #
@login_required
def client_dashboard(request):
    consultations = Consultation.objects.filter(client=request.user)
    documents = Document.objects.filter(user=request.user)
    return render(request, 'dashboard/client.html', {
        'consultations': consultations,
        'documents': documents
    })

@login_required
def provider_dashboard(request):
    services = Service.objects.filter(provider=request.user)
    consultations = Consultation.objects.filter(slot__provider=request.user)
    reviews = Review.objects.filter(service__provider=request.user)
    return render(request, 'dashboard/provider.html', {
        'services': services,
        'consultations': consultations,
        'reviews': reviews
    })
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
# views.py
@login_required
def dashboard(request):
    if request.user.role == User.Role.PROVIDER:
        # لوحة مقدم الخدمة
        services = Service.objects.filter(provider=request.user)
        consultations = Consultation.objects.filter(slot__provider=request.user)
        bookings = Booking.objects.filter(service__provider=request.user)
        reviews = Review.objects.filter(service__provider=request.user)
        
        # حساب الإحصائيات
        active_services = services.filter(is_active=True).count()
        monthly_consultations = consultations.filter(
            created_at__month=timezone.now().month
        ).count()
        monthly_bookings = bookings.filter(
            created_at__month=timezone.now().month,
            status__in=['confirmed', 'completed']
        ).count()
        
        avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        
        # الطلبات الجديدة
        new_consultation_requests = ConsultationRequest.objects.filter(
            consultant=request.user,
            status='pending'
        )[:5]
        
        new_bookings = bookings.filter(
            status='pending'
        )[:5]
        
        # المراجعات الحديثة
        recent_reviews = reviews.order_by('-created_at')[:3]
        
        # المواعيد القادمة
        upcoming_appointments = consultations.filter(
            slot__start_time__gte=timezone.now(),
            status='confirmed'
        ).union(
            bookings.filter(
                slot__start_time__gte=timezone.now(),
                status='confirmed'
            )
        ).order_by('slot__start_time')[:5]
        
        # حساب معدلات الأداء
        total_bookings = bookings.count()
        confirmed_bookings = bookings.filter(status='confirmed').count()
        completed_bookings = bookings.filter(status='completed').count()
        
        booking_rate = round((confirmed_bookings / total_bookings * 100), 2) if total_bookings > 0 else 0
        completion_rate = round((completed_bookings / total_bookings * 100), 2) if total_bookings > 0 else 0
        satisfaction_rate = round(avg_rating * 20, 1) if avg_rating > 0 else 0  # تحويل من 5 إلى 100
        
        return render(request, 'dashboard/provider.html', {
            'active_services': active_services,
            'monthly_consultations': monthly_consultations,
            'monthly_bookings': monthly_bookings,
            'avg_rating': round(avg_rating, 1),
            'new_consultation_requests': new_consultation_requests,
            'new_bookings': new_bookings,
            'recent_reviews': recent_reviews,
            'upcoming_appointments': upcoming_appointments,
            'booking_rate': booking_rate,
            'satisfaction_rate': satisfaction_rate,
            'completion_rate': completion_rate
        })
    else:
        # لوحة العميل
        consultations = Consultation.objects.filter(client=request.user)
        bookings = Booking.objects.filter(client=request.user)
        documents = Document.objects.filter(user=request.user)
        
        # حساب الإحصائيات
        active_consultations = consultations.filter(
            status__in=['pending', 'confirmed']
        ).count()
        
        active_bookings = bookings.filter(
            status__in=['pending', 'confirmed'],
            slot__start_time__gte=timezone.now()
        ).count()
        
        documents_count = documents.count()
        
        unread_notifications = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).count()
        
        # المواعيد القادمة
        upcoming_consultations = consultations.filter(
            slot__start_time__gte=timezone.now(),
            status='confirmed'
        ).order_by('slot__start_time')[:3]
        
        upcoming_bookings = bookings.filter(
            slot__start_time__gte=timezone.now(),
            status='confirmed'
        ).order_by('slot__start_time')[:3]
        
        # الوثائق المهمة
        important_documents = documents.filter(
            is_important=True,
            reminder_date__isnull=False
        ).order_by('reminder_date')[:3]
        
        # حساب الأيام المتبقية لكل وثيقة
        for doc in important_documents:
            doc.reminder_days = (doc.reminder_date - timezone.now().date()).days
            doc.is_urgent = doc.reminder_days <= 3
        
        return render(request, 'dashboard/client.html', {
            'active_consultations': active_consultations,
            'active_bookings': active_bookings,
            'documents_count': documents_count,
            'unread_notifications': unread_notifications,
            'upcoming_consultations': upcoming_consultations,
            'upcoming_bookings': upcoming_bookings,
            'important_documents': important_documents
        })

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
def inquiries_list(request):
    inquiries = ConsultationRequest.objects.filter(client=request.user)
    return render(request, 'inquiries/list.html', {
        'inquiries': inquiries
    })

@login_required
def switch_role(request):
    if request.method == 'POST':
        request.user.switch_role()
        messages.success(request, 'تم تغيير الدور بنجاح!')
    return redirect('dashboard')
# ---- إدارة الخدمات ---- #
@login_required
def service_list(request):
    services = Service.objects.filter(provider=request.user)
    return render(request, 'services/list.html', {'services': services})

def create_service(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = request.user
            
            # إنشاء slug فريد إذا لم يتم توفيره
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
        form = ServiceForm(request.POST, instance=service)
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
            messages.success(request, 'تم إضافة الموعد بنجاح!')
            return redirect('slot_list')
    else:
        form = ConsultationSlotForm(user=request.user)
    return render(request, 'consultations/create_slot.html', {'form': form})

# ---- البحث والاكتشاف ---- #
def browse_services(request):
    category_id = request.GET.get('category')
    query = request.GET.get('q')
    
    services = Service.objects.filter(is_active=True)
    
    if category_id:
        services = services.filter(category_id=category_id)
    
    if query:
        services = services.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
         Q(category__name__icontains=query)|
        Q(provider__first_name__icontains=query) |
        Q(provider__last_name__icontains=query) |
        Q(provider__full_name__icontains=query)|
        Q(provider__email__icontains=query))
    
    
    categories = ServiceCategory.objects.annotate(
        service_count=Count('service')
    ).order_by('-service_count')
    
    paginator = Paginator(services, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'services/browse.html', {
        'services': page_obj,
        'categories': categories,
        'selected_category': int(category_id) if category_id else None,
        'search_query': query or '',
        'request': request
    })

def service_detail(request, slug):
    service = get_object_or_404(Service, slug=slug, is_active=True)
    reviews = service.reviews.all().order_by('-created_at')
    similar_services = Service.objects.filter(
        category=service.category,
        is_active=True
    ).exclude(id=service.id).order_by('?')[:3]
    # حساب متوسط التقييمات
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    # التحقق إذا كان المستخدم قد قام بتقييم هذه الخدمة من قبل
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
            review.service = service
            review.reviewer = request.user
            review.save()
            messages.success(request, 'شكراً لتقييمك هذه الخدمة!')
            return redirect('service_detail', slug=slug)
    else:
        form = ReviewForm(instance=user_review)
    
    return render(request, 'services/detail.html', {
        'service': service,
        'similar_services':similar_services,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'user_review': user_review,
        'form': form
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
def request_consultation(request):
    if request.method == 'POST':
        form = ConsultationRequestForm(request.POST)
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.client = request.user
            
            # تعيين المستشار بناءً على مقدم الخدمة المختارة
            consultation.consultant = consultation.service.provider
            
            consultation.save()
            
            # إرسال إشعار للمستشار
            Notification.objects.create(
                user=consultation.consultant,
                message=f"لديك طلب استشارة جديد من {request.user.username}",
                link=f"/consultations/{consultation.id}/"
            )
            
            messages.success(request, 'تم إرسال طلب الاستشارة بنجاح!')
            return redirect('consultation_list')
    else:
        form = ConsultationRequestForm()
    
    return render(request, 'consultations/request.html', {'form': form})

@login_required
def consultant_detail(request, pk):
    consultant = get_object_or_404(Consultant, pk=pk)
    
    # جلب المواعيد المتاحة للمستشار
    available_slots = ConsultationSlot.objects.filter(
        provider=consultant.user,
        is_booked=False,
        start_time__gt=timezone.now()  # فقط المواعيد المستقبلية
    ).order_by('start_time')
    
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'consultation_request':
            # معالجة نموذج إرسال الاستشارة
            category = get_object_or_404(ServiceCategory, id=request.POST.get('category'))
            question = request.POST.get('question')
            
            ConsultationRequest.objects.create(
                client=request.user,
                consultant=consultant.user,
                category=category,
                question=question
            )
            
            messages.success(request, 'تم إرسال استشارتك بنجاح!')
            return redirect('consultation_list')
    
    return render(request, 'services/consultant_detail.html', {
        'consultant': consultant,
        'available_slots': available_slots
    })

@login_required
def book_consultation(request, slot_id):
    slot = get_object_or_404(ConsultationSlot, id=slot_id, is_booked=False)
    
    # إذا كان الموعد غير متاح (محجوز مسبقًا) أو انتهى وقته
    if slot.start_time <= timezone.now():
        messages.error(request, 'عذرًا، هذا الموعد لم يعد متاحًا.')
        return redirect('consultants_list')
    
    # تأكد أن المستخدم الحالي ليس هو مقدم الخدمة
    if slot.provider == request.user:
        messages.error(request, 'لا يمكنك حجز موعد خاص بك.')
        return redirect('consultants_list')
    
    # إنشاء استشارة جديدة
    consultation = Consultation.objects.create(
        slot=slot,
        client=request.user,
        service=slot.service,  # إذا كان الموعد مرتبطًا بخدمة معينة
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
    
    return render(request, 'faq/list.html', {
        'featured_faqs': featured_faqs,
        'other_faqs': other_faqs
    })

def home(request):
    return render(request , 'home.html')



# views.py
def consultants_list(request):
    consultants = Consultant.objects.filter(available=True)
    categories = ServiceCategory.objects.all()
    
    # Filtering
    category_id = request.GET.get('category')
    search_query = request.GET.get('q')
    
    if category_id:
        consultants = consultants.filter(categories__id=category_id)
    if search_query:
        consultants = consultants.filter(
            Q(user__full_name__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(categories__name__icontains=search_query)
        ).distinct()
    
    return render(request, 'services/consultants.html', {
        'consultants': consultants,
        'categories': categories
    })

@login_required
def consultant_detail(request, pk):
    consultant = get_object_or_404(Consultant, pk=pk)
    
    if request.method == 'POST':
        category = get_object_or_404(ServiceCategory, id=request.POST.get('category'))
        question = request.POST.get('question')
        
        ConsultationRequest.objects.create(
            client=request.user,
            consultant=consultant.user,
            category=category,
            question=question
        )
        
        messages.success(request, 'تم إرسال استشارتك بنجاح!')
        return redirect('consultation_list')
    
    return render(request, 'services/consultant_detail.html', {
        'consultant': consultant
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
            message=f"تم الرد على استشارتك من قبل {request.user.username}",
            link=f"/consultations/{consultation.id}/"
        )
        
        messages.success(request, 'تم حفظ الرد بنجاح!')
        return redirect('consultation_detail', pk=pk)
    
    return render(request, 'consultations/respond.html', {
        'consultation': consultation
    })


@login_required
def consultation_detail(request, pk):
    consultation = get_object_or_404(ConsultationRequest, pk=pk)
    
    # Check access permissions
    if request.user not in [consultation.client, consultation.consultant]:
        messages.error(request, 'ليس لديك صلاحية لعرض هذه الاستشارة.')
        return redirect('dashboard')
    
    return render(request, 'consultations/detail.html', {
        'consultation': consultation
    })



@login_required
def create_service(request):
    categories = ServiceCategory.objects.all()
    
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = request.user
            service.save()
            messages.success(request, 'تم إضافة الخدمة بنجاح!')
            return redirect('service_list')
    else:
        form = ServiceForm()
    
    return render(request, 'services/create.html', {
        'form': form,
        'categories': categories
    })

# views.py
@login_required
def request_consultation(request, service_id):
    service = get_object_or_404(Service, id=service_id)
    if request.method == 'POST':
        form = ConsultationRequestForm(request.POST)
        if form.is_valid():
            consultation = form.save(commit=False)
            consultation.client = request.user
            consultation.service = service
            consultation.save()
            return redirect('consultation_list')
    else:
        form = ConsultationRequestForm()
    
    return render(request, 'consultations/request.html', {
        'form': form,
        'service': service
    })

@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(client=request.user).order_by('-created_at')
    
    # تصفية الحجوزات حسب الحالة
    status = request.GET.get('status')
    if status in ['pending', 'confirmed', 'completed', 'cancelled']:
        bookings = bookings.filter(status=status)
    
    # الترقيم
    paginator = Paginator(bookings, 10)  # 10 حجوزات في الصفحة
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


def handler404(request, exception):
    return render(request, "404.html", status=404)



def custom_logout(request):
    logout(request)
    messages.success(request, 'تم تسجيل الخروج بنجاح')
    return redirect('home')


from django.http import JsonResponse

def autocomplete_services(request):
    query = request.GET.get('term', '')
    services = Service.objects.filter(
        Q(title__icontains=query) |
        Q(description__icontains=query) |
        Q(provider__full_name__icontains=query),
        is_active=True
    ).distinct()[:10]  # الحد الأقصى للنتائج
    
    results = []
    for service in services:
        results.append({
            'id': service.id,
            'label': service.title,
            'value': service.title,
            'category': service.category.name,
            'url': service.get_absolute_url()
        })
    return JsonResponse(results, safe=False)
