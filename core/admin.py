from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User, Profile, ServiceCategory, Service,
    Consultant, ConsultationSlot, Consultation,
    Document, Notification, Review, Advertisement,
    FAQ, ConsultationRequest
)

class CustomUserAdmin(UserAdmin):
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('معلومات الشخصية', {'fields': ('full_name', 'phone', 'role')}),
        ('الصلاحيات', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('تواريخ مهمة', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('full_name', 'email', 'phone', 'role', 'password1', 'password2'),
        }),
    )
    list_display = ('full_name', 'email', 'role', 'is_staff')
    search_fields = ('full_name', 'email')
    ordering = ('full_name',)

class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    search_fields = ('user__username', 'bio')
    raw_id_fields = ('user',)

class ServiceAdmin(admin.ModelAdmin):
    list_display = ('title', 'provider', 'category', 'price', 'is_active')
    list_filter = ('category', 'is_active')
    search_fields = ('title', 'description')
    prepopulated_fields = {'slug': ('title',)}
    raw_id_fields = ('provider', 'category')

class ConsultantAdmin(admin.ModelAdmin):
    list_display = ('user', 'available', 'rating')
    list_filter = ('available',)
    filter_horizontal = ('categories',)
    raw_id_fields = ('user',)

class ConsultationSlotAdmin(admin.ModelAdmin):
    list_display = ('provider', 'start_time', 'end_time', 'is_booked')
    list_filter = ('is_booked',)
    raw_id_fields = ('provider',)

class ConsultationAdmin(admin.ModelAdmin):
    list_display = ('slot', 'client', 'service', 'status', 'created_at')
    list_filter = ('status',)
    raw_id_fields = ('slot', 'client', 'service')

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'is_important', 'reminder_date')
    list_filter = ('is_important',)
    search_fields = ('title', 'description')
    raw_id_fields = ('user',)

class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read',)
    raw_id_fields = ('user',)

class ReviewAdmin(admin.ModelAdmin):
    list_display = ('service', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating',)
    raw_id_fields = ('service', 'reviewer')

class AdvertisementAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'is_active', 'start_date', 'end_date')
    list_filter = ('is_active',)
    raw_id_fields = ('owner',)

class FAQAdmin(admin.ModelAdmin):
    list_display = ('question', 'is_featured')
    list_filter = ('is_featured',)
    search_fields = ('question', 'answer')

class ConsultationRequestAdmin(admin.ModelAdmin):
    list_display = ('client', 'consultant', 'category', 'status', 'created_at')
    list_filter = ('status', 'category')
    raw_id_fields = ('client', 'consultant', 'category')

# تسجيل النماذج مرة واحدة فقط
admin.site.register(User, CustomUserAdmin)
admin.site.register(Profile, ProfileAdmin)
admin.site.register(ServiceCategory)
admin.site.register(Service, ServiceAdmin)
admin.site.register(Consultant, ConsultantAdmin)
admin.site.register(ConsultationSlot, ConsultationSlotAdmin)
admin.site.register(Consultation, ConsultationAdmin)
admin.site.register(Document, DocumentAdmin)
admin.site.register(Notification, NotificationAdmin)
admin.site.register(Review, ReviewAdmin)
admin.site.register(Advertisement, AdvertisementAdmin)
admin.site.register(FAQ, FAQAdmin)
admin.site.register(ConsultationRequest, ConsultationRequestAdmin)