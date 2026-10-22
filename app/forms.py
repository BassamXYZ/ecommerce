from django import forms


class CheckoutForm(forms.Form):
    first_name = forms.CharField(max_length=100, strip=True)
    last_name = forms.CharField(max_length=100, strip=True)
    email = forms.EmailField(max_length=254)
    phone = forms.CharField(max_length=30, required=False, strip=True)
    street = forms.CharField(max_length=200, strip=True)
    city = forms.CharField(max_length=100, strip=True)
    postal_code = forms.CharField(max_length=20, strip=True)
    country = forms.CharField(max_length=100, strip=True)
