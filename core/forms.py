from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')

    class Meta:
        model = User
        fields = ('first_name', 'username', 'email', 'password1', 'password2') 
        labels = {
            'username': 'Логин',
            'first_name': 'Ваше имя',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists(): raise forms.ValidationError("Пользователь с такой почтой уже зарегестрирован.")
        return email