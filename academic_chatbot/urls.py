from django.urls import path

from .views import AcademicChatbotQueryView


urlpatterns = [
    path(
        "query/",
        AcademicChatbotQueryView.as_view(),
        name="academic-chatbot-query",
    ),
]