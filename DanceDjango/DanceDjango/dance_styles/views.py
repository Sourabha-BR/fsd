from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
from .models import DanceStyle, ClassSlot, Registration, Instructor, Video, VideoProgress, VideoComment, Event, EventRegistration
from django.utils import timezone
from .models import Event
from datetime import timedelta

# Create your views here.
from .models import DanceStyle, ClassSlot, Registration

@login_required
def register_class(request):
    if request.method == 'POST':
        dance_style_id = request.POST.get('dance_style')
        class_slot_id = request.POST.get('class_slot')
        
        name = request.POST.get('name')
        if dance_style_id and class_slot_id and name:
            dance_style = get_object_or_404(DanceStyle, id=dance_style_id)
            class_slot = get_object_or_404(ClassSlot, id=class_slot_id)
            
            # Update user's name
            request.user.first_name = name
            request.user.save()
            
            # Create registration
            registration = Registration.objects.create(
                user=request.user,
                dance_style=dance_style,
                class_slot=class_slot
            )
            
            return redirect('dance_styles:payment', registration_id=registration.id)
    
    dance_styles = DanceStyle.objects.all()
    return render(request, 'dance_styles/register.html', {'dance_styles': dance_styles})

@login_required
def payment_view(request, registration_id):
    registration = get_object_or_404(Registration, id=registration_id, user=request.user)
    return render(request, 'dance_styles/payment.html', {'registration': registration})

@login_required
def confirm_payment(request, registration_id):
    if request.method == 'POST':
        registration = get_object_or_404(Registration, id=registration_id, user=request.user)
        registration.payment_status = 'completed'
        registration.save()
        messages.success(request, 'Payment confirmed! Welcome to the dance class!')
        return redirect('dance_styles:home')

def get_dance_style_details(request, style_id):
    dance_style = get_object_or_404(DanceStyle, id=style_id)
    class_slots = dance_style.class_slots.all()
    
    return JsonResponse({
        'choreographer': dance_style.choreographer,
        'registration_fee': str(dance_style.registration_fee),
        'class_slots': [
            {
                'id': slot.id,
                'day': slot.day,
                'start_time': slot.start_time.strftime('%I:%M %p'),
                'end_time': slot.end_time.strftime('%I:%M %p')
            } for slot in class_slots
        ]
    })

@login_required(login_url='dance_styles:login')
def home(request):
    """
    Home page view that displays all dance styles (dashboard)
    """
    dance_styles = DanceStyle.objects.all()
    return render(request, 'dance_styles/home.html', {'dance_styles': dance_styles})

@login_required(login_url='dance_styles:login')
def dance_style_detail(request, style_id):
    """
    Detail view for a specific dance style
    """
    dance_style = get_object_or_404(DanceStyle, id=style_id)
    return render(request, 'dance_styles/dance_style_detail.html', {'dance_style': dance_style})

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dance_styles:home')
        else:
            return render(request, 'dance_styles/login.html', {'error': 'Invalid username or password'})
    return render(request, 'dance_styles/login.html')

def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            return render(request, 'dance_styles/signup.html', {'error': 'Passwords do not match'})
        if User.objects.filter(username=username).exists():
            return render(request, 'dance_styles/signup.html', {'error': 'Username already exists'})
        user = User.objects.create_user(username=username, password=password1)
        login(request, user)
        return redirect('dance_styles:home')
    return render(request, 'dance_styles/signup.html')

def about(request):
    """About Us page view"""
    return render(request, 'dance_styles/about.html')

def instructors(request):
    """Instructors page view"""
    instructors = Instructor.objects.all().prefetch_related('dance_styles')
    return render(request, 'dance_styles/instructors.html', {'instructors': instructors})

def contact(request):
    """Contact Us page view with form handling"""
    if request.method == 'POST':
        name = request.POST.get('name')
        email = request.POST.get('email')
        subject = request.POST.get('subject')
        message = request.POST.get('message')
        
        # Email content
        email_message = f"Name: {name}\nEmail: {email}\nMessage: {message}"
        
        try:
            # Send email
            send_mail(
                subject,
                email_message,
                email,  # From email
                ['info@dancestudio.com'],  # To email
                fail_silently=False,
            )
            messages.success(request, 'Your message has been sent successfully!')
            return redirect('dance_styles:contact')
        except Exception as e:
            messages.error(request, 'There was an error sending your message. Please try again later.')
    
    return render(request, 'dance_styles/contact.html')

def logout_view(request):
    logout(request)
    return redirect('dance_styles:login')

@login_required
def events_list(request):
    featured_events = Event.objects.filter(is_featured=True, date__gte=timezone.now().date()).order_by('date')[:3]
    upcoming_events = Event.objects.filter(date__gte=timezone.now().date()).order_by('date')
    past_events = Event.objects.filter(date__lt=timezone.now().date()).order_by('-date')[:5]
    
    context = {
        'featured_events': featured_events,
        'upcoming_events': upcoming_events,
        'past_events': past_events,
    }
    return render(request, 'dance_styles/events.html', context)

@login_required
def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    user_registered = EventRegistration.objects.filter(user=request.user, event=event).exists()
    
    if request.method == 'POST' and not user_registered and event.is_registration_open():
        # Create event registration
        registration = EventRegistration.objects.create(
            user=request.user,
            event=event,
            payment_status='pending'
        )
        # Decrease available slots
        event.available_slots -= 1
        event.save()
        
        messages.success(request, f'Successfully registered for {event.title}! Your ticket number is {registration.ticket_number}')
        return redirect('dance_styles:event_detail', event_id=event.id)
    
    context = {
        'event': event,
        'user_registered': user_registered,
    }
    return render(request, 'dance_styles/event_detail.html', context)

@login_required
def my_events(request):
    user_registrations = EventRegistration.objects.filter(user=request.user).order_by('-registration_date')
    context = {
        'registrations': user_registrations,
    }
    return render(request, 'dance_styles/my_events.html', context)

@login_required
def video_library(request):
    # Get all videos
    videos = Video.objects.all().order_by('-created_at')
    
    # Get progress for the current user
    progress_map = {}
    if request.user.is_authenticated:
        progress_entries = VideoProgress.objects.filter(user=request.user)
        for progress in progress_entries:
            # Calculate percentage watched
            if progress.video.duration:
                percentage = (progress.watched_duration.total_seconds() / progress.video.duration.total_seconds()) * 100
                progress_map[progress.video.id] = round(percentage)
    
    # Separate videos by type
    live_videos = videos.filter(video_type='live', scheduled_time__gt=timezone.now())
    recorded_videos = videos.filter(video_type='recorded')
    
    context = {
        'live_videos': live_videos,
        'recorded_videos': recorded_videos,
        'progress_map': progress_map
    }
    return render(request, 'dance_styles/video_library.html', context)

@login_required
def video_detail(request, video_id):
    video = get_object_or_404(Video, pk=video_id)
    
    if video.is_premium and not request.user.is_premium:
        messages.error(request, 'This video is only available to premium members.')
        return redirect('dance_styles:video_library')
    
    user_progress, created = VideoProgress.objects.get_or_create(
        user=request.user,
        video=video
    )
    
    comments = video.comments.all().order_by('timestamp', 'created_at')
    
    if request.method == 'POST':
        if 'comment' in request.POST:
            content = request.POST.get('comment')
            timestamp = request.POST.get('timestamp')
            if content:
                VideoComment.objects.create(
                    user=request.user,
                    video=video,
                    content=content,
                    timestamp=timestamp if timestamp else None
                )
                return redirect('dance_styles:video_detail', video_id=video_id)
        
        elif 'progress' in request.POST:
            watched_duration = request.POST.get('watched_duration')
            if watched_duration:
                user_progress.watched_duration = timezone.timedelta(seconds=float(watched_duration))
                user_progress.completed = float(watched_duration) >= video.duration.total_seconds() * 0.9
                user_progress.save()
                return JsonResponse({'status': 'success'})
    
    context = {
        'video': video,
        'progress': user_progress,
        'comments': comments,
        'is_live': video.is_live_now()
    }
    return render(request, 'dance_styles/video_detail.html', context)

@login_required
def update_video_progress(request, video_id):
    if request.method == 'POST':
        video = get_object_or_404(Video, pk=video_id)
        progress = VideoProgress.objects.get_or_create(user=request.user, video=video)[0]
        
        watched_duration = request.POST.get('watched_duration')
        if watched_duration:
            progress.watched_duration = timezone.timedelta(seconds=float(watched_duration))
            progress.completed = float(watched_duration) >= video.duration.total_seconds() * 0.9
            progress.save()
            
            return JsonResponse({
                'status': 'success',
                'progress': {
                    'watched_duration': progress.watched_duration.total_seconds(),
                    'completed': progress.completed
                }
            })
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def schedule(request):
    today = timezone.now().date()
    # Get all upcoming classes for the next 7 days
    upcoming_classes = ClassSlot.objects.filter(
        date__gte=today,
        date__lte=today + timedelta(days=7)
    ).order_by('date', 'start_time')
    
    # Group classes by date
    classes_by_date = {}
    for class_slot in upcoming_classes:
        date_str = class_slot.date.strftime('%Y-%m-%d')
        if date_str not in classes_by_date:
            classes_by_date[date_str] = []
        classes_by_date[date_str].append(class_slot)
    
    # Get all live video classes scheduled for the next 7 days
    live_classes = Video.objects.filter(
        video_type='live',
        scheduled_time__date__gte=today,
        scheduled_time__date__lte=today + timedelta(days=7)
    ).order_by('scheduled_time')
    
    context = {
        'classes_by_date': classes_by_date,
        'live_classes': live_classes,
        'today': today,
    }
    return render(request, 'dance_styles/schedule.html', context)
