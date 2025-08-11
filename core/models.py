from django.contrib.auth.models import AbstractUser ,BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify  # Import slugify
import uuid
from django.utils import timezone 
from django.db.models import Avg
# models.py

class UserManager(BaseUserManager):
    def create_user(self, email, full_name, phone, password=None, **extra_fields):
        if not email:
            raise ValueError("يجب إدخال البريد الإلكتروني")
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('المستخدم الخارق يجب أن يكون is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('المستخدم الخارق يجب أن يكون is_superuser=True.')

        return self.create_user(email, full_name, phone, password, **extra_fields)

class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = 'client', _('عميل')
        PROVIDER = 'provider', _('مقدم خدمة')
    username = None
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CLIENT
    )
    full_name = models.CharField(max_length=255,verbose_name='full_name')
    phone = models.CharField(max_length=20, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    email = models.EmailField(
        verbose_name=' email',
        unique=True,  # أضف هذه السطر
        error_messages={
            'unique': 'هذا البريد الإلكتروني مستخدم بالفعل.'
        }
    )
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name', 'phone']
    objects = UserManager()
    def switch_role(self):
        if self.role == self.Role.CLIENT:
            self.role = self.Role.PROVIDER
            Consultant.objects.get_or_create(
                user=self,
                defaults={'available': True}
            )
        elif self.role == self.Role.PROVIDER:
            self.role = self.Role.CLIENT
        self.save()
# Add the missing Consultant model


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_image = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(blank=True)
    address = models.TextField(blank=True)
    website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s Profile"

class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name_plural = "Service Categories"
    
    def __str__(self):
        return self.name

class Service(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField()
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration = models.DurationField(help_text="Estimated service duration")
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='services')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        indexes = [
            models.Index(fields=['title']),
            models.Index(fields=['description']),
        ]
    def save(self, *args, **kwargs):
        if not self.slug:
            # إنشاء slug من العنوان مع إضافة جزء عشوائي لتجنب التكرار
            base_slug = slugify(self.title)
            unique_slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
            self.slug = unique_slug
        self.is_active = True
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.title} by {self.provider.username}"
    
# models.py
class Consultant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    categories = models.ManyToManyField(ServiceCategory)
    bio = models.TextField()
    profile_image = models.ImageField(upload_to='consultants/' , null=True)
    available = models.BooleanField(default=True)
    rating = models.FloatField(default=0)
    
    @property
    def avg_rating(self):
        reviews = Review.objects.filter(service__provider=self.user)
        avg = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        return round(avg, 1)

    @property
    def review_count(self):
        return Review.objects.filter(service__provider=self.user).count()
    def __str__(self):
        return f"{self.user.username} - مستشار"
    
class ConsultationSlot(models.Model):
    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='slots')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_booked = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['start_time']
    
    def __str__(self):
        return f"{self.provider.username} - {self.start_time}"

class Consultation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('قيد الانتظار')
        CONFIRMED = 'confirmed', _('تم التأكيد')
        COMPLETED = 'completed', _('منتهية')
        CANCELLED = 'cancelled', _('ملغاة')
    
    slot = models.OneToOneField(ConsultationSlot, on_delete=models.PROTECT)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_consultations')
    service = models.ForeignKey(Service, on_delete=models.CASCADE , blank=True, null=True)
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if self.status == self.Status.CONFIRMED:
            self.slot.is_booked = True
            self.slot.save()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Consultation #{self.id} - {self.client.username} with {self.slot.provider.username}"

class Document(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='documents')
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    description = models.TextField(blank=True)
    reminder_date = models.DateField(null=True, blank=True)
    is_important = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.title

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    link = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.user.username}"

class Review(models.Model):
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_reviews')
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('service', 'reviewer')
    
    def __str__(self):
        return f"Review for {self.service.title} by {self.reviewer.username}"

class Advertisement(models.Model):
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to='ads/')
    link = models.URLField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get_active_ads(cls, limit=3):
        """Alternative as class method"""
        now = timezone.now().date()
        return cls.objects.filter(
            is_active=True,
            start_date__lte=now,
            end_date__gte=now
        ).order_by('-created_at')[:limit]
    def __str__(self):
        return self.title

class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "FAQ"
        verbose_name_plural = "FAQs"
        ordering = ['-is_featured', 'question']
    
    def __str__(self):
        return self.question

# models.py
class ConsultationRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'قيد الانتظار'),
        ('accepted', 'مقبول'),
        ('rejected', 'مرفوض'),
        ('completed', 'مكتمل')
    ]
    
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='client_requests')
    consultant = models.ForeignKey(User, on_delete=models.CASCADE, related_name='consultant_requests')
    question = models.TextField()
    response = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"استشارة #{self.id} - {self.client.username} إلى {self.consultant.username}"
    
    def can_respond(self, user):
        return self.consultant == user and self.status in ['pending', 'accepted']
    

class Booking(models.Model):
    class Status(models.TextChoices):
        PENDING = 'pending', _('قيد الانتظار')
        CONFIRMED = 'confirmed', _('تم التأكيد')
        COMPLETED = 'completed', _('منتهية')
        CANCELLED = 'cancelled', _('ملغاة')
    
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    slot = models.ForeignKey(ConsultationSlot, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"حجز #{self.id} - {self.client.username} لـ {self.service.title}"
    
    def get_status_display(self):
        return dict(self.Status.choices)[self.status]
