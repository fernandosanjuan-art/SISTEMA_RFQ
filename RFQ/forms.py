from django import forms

from .models import DrawingAnalysis


class DrawingUploadForm(forms.ModelForm):

    class Meta:

        model = DrawingAnalysis

        fields = ['uploaded_file']

