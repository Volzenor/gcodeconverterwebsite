from django import forms

class GForm(forms.Form):
    file = forms.ImageField()
    Max_Y = forms.DecimalField()
    Max_X = forms.DecimalField()
    Machine_Sensivity = forms.DecimalField()
    Cutting_Tool_Diameter = forms.DecimalField()
    Cutting_Tool_Team_Number = forms.IntegerField()
    S = forms.IntegerField()
    F = forms.IntegerField()
    Max_Z = forms.DecimalField()
    Min_Z = forms.DecimalField()
    Is_it_black_and_white= forms.BooleanField(required=False)

class SimForm(forms.Form):
    file = forms.FileField()
    Cutting_Tool_Diameter = forms.DecimalField()