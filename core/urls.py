from django.urls import path
from . import views

urlpatterns = [
    # Authentication URLs
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.custom_logout, name='logout'),
    
    # Profile URLs
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('provider-profile/', views.provider_profile, name='provider_profile'),
    
    # Dashboard URL
    path('dashboard/', views.dashboard, name='dashboard'),
    path('provider-dashboard/', views.provider_dashboard, name='provider_dashboard'),
    path('client-dashboard/', views.client_dashboard, name='client_dashboard'),
    path('switch-role/', views.switch_role, name='switch_role'),
    
    # Service Management URLs
    path('services/', views.service_list, name='service_list'),
    path('services/create/', views.create_service, name='create_service'),
    path('services/update/<int:pk>/', views.update_service, name='update_service'),
    
    # Consultation Slot URLs
    path('slots/', views.slot_list, name='slot_list'),
    path('slots/create/', views.create_slot, name='create_slot'),
    
    # Consultants URLs
    path('consultants/', views.browse_consultants, name='browse_consultants'),
    path('consultant/<int:pk>/', views.consultant_detail, name='consultant_detail'),
    path('consultant/<int:consultant_id>/request/', views.request_consultation, name='request_consultation'),
    path('book/<int:slot_id>/', views.book_consultation, name='book_consultation'),
    
    # Document Management URLs
    path('documents/', views.document_list, name='document_list'),
    path('documents/upload/', views.upload_document, name='upload_document'),
    path('documents/delete/<int:pk>/', views.delete_document, name='delete_document'),
    
    # Consultation System URLs
    path('consultations/', views.consultation_list, name='consultation_list'),
    path('consultations/<int:pk>/', views.consultation_detail, name='consultation_detail'),
    path('consultations/<int:pk>/respond/', views.respond_to_consultation, name='respond_consultation'),
    
    # Booking URLs
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('booking/<int:pk>/', views.booking_detail, name='booking_detail'),
    path('booking/<int:pk>/cancel/', views.cancel_booking, name='cancel_booking'),
    
    # Notification System URL
    path('notifications/', views.notifications, name='notifications'),
    
    # FAQ URL
    path('faq/', views.faq_list, name='faq_list'),
    
    # Home URL
    path('', views.home, name='home'),
    
    # Switch Role
    path('switch-role/', views.switch_role, name='switch_role'),
    
    # Autocomplete
    path('consultants/autocomplete/', views.autocomplete_consultants, name='autocomplete_consultants'),
    
    # Error Handler
    path('404/', views.handler404),
]
