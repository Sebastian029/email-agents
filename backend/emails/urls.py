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

]