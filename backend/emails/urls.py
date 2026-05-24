from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views


router = DefaultRouter()
router.register(r'mailboxes', views.MailboxViewSet, basename='mailbox')

urlpatterns = [
    path('', include(router.urls)),

    path('fetch/', views.FetchEmailsView.as_view(), name='fetch_emails'),

    path('list/<int:mailbox_id>/', views.ListEmailsView.as_view(), name='list_emails'),
    path('list/', views.ListEmailsView.as_view(), name='list_all_emails'),
    path('list-test/', views.TestListEmailsView.as_view(), name='list_all_emails'),
    path('send/', views.SendEmailView.as_view(), name='send_email'),
    path('clear-emails/', views.ClearEmailsView.as_view(), name='clear-emails'),
    path('thread/<int:email_id>/', views.EmailThreadView.as_view(), name='email-thread'),
    path('thread/<int:email_id>/hide/', views.HideThreadView.as_view(), name='hide-thread'),
    path('thread/<int:email_id>/unhide/', views.UnhideThreadView.as_view(), name='unhide-thread'),
    path('thread/<int:email_id>/delete/', views.DeleteThreadView.as_view(), name='delete-thread'),
    path('thread-summary/<int:email_id>/', views.ThreadSummaryView.as_view(), name='thread-summary'),
    path('<int:email_id>/hide/', views.HideEmailView.as_view(), name='hide-email'),
    path('<int:email_id>/unhide/', views.UnhideEmailView.as_view(), name='unhide-email'),
    path('<int:email_id>/delete/', views.DeleteEmailView.as_view(), name='delete-email'),


]