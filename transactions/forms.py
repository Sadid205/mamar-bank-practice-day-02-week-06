from django import forms
from .models import Transaction


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['amount','transaction_type']

    def __init__(self,*args,**kwargs):
        self.account = kwargs.pop('account') # account  value ke pop kore anlam
        super().__init__(*args,**kwargs)
        self.fields['transaction_type'].disabled = True # ei field disable thakbe 
        self.fields['transaction_type'].widget = forms.HiddenInput() # user er theke hide kora thakbe

    def save(self,commit=True):
        self.instance.account = self.account
        self.instance.balance_after_transaction = self.account.balance 
        return super().save() 
    

class DepositForm(TransactionForm):

    def clean_amount(self): #amount field ke filter korbo
        min_deposit_amount = 100
        amount = self.cleaned_data.get('amount') # user er fill up kora form theke amra ammount field er value ke niye aslam
        if amount < min_deposit_amount:
            raise forms.ValidationError(
                f'You need to deposit at least {min_deposit_amount} $'
            )
        return amount

class WithdrawForm(TransactionForm):

    def clean_amount(self):
        account = self.account
        min_withdraw_amount = 500
        max_withdraw_amount = 20000
        balance = account.balance # 1000
        amount = self.cleaned_data.get('amount')

        if amount < min_withdraw_amount:
            raise forms.ValidationError(
                f'You can withdraw at least {min_withdraw_amount} $'
            )
        
        if amount > max_withdraw_amount:
            raise forms.ValidationError(
                f'You can withdraw at most {max_withdraw_amount} $'
            )
        
        if amount > balance: # amount = 5000, tar balance 200
            raise forms.ValidationError(
                f'You have {balance} $ in your account. '
                'You can not withdraw more than your account balance'
            )
        if Transaction.objects.filter(is_bankrupt=True).exists() :
           raise forms.ValidationError('Now this bank is bankrupt.You can not withdraw any amount at this moment.')
        
        return amount
    
class LoanRequestForm(TransactionForm):
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')

        return amount 
    
class TransferBalanceForm(TransactionForm):
    account_number = forms.IntegerField()
    def clean_account_number(self):
        account_number = self.cleaned_data.get('account_number')
        return account_number
    def clean_amount(self):
        account = self.account
        min_transfer_amount = 500
        max_transfer_amount = 20000
        amount = self.cleaned_data.get('amount')
        if amount < min_transfer_amount:
            raise forms.ValidationError(
                f'You can transfer at least {min_transfer_amount} $'
            )
        if amount > max_transfer_amount:
            raise forms.ValidationError(
                f'You can transfer at most {max_transfer_amount} $'
            )
        if amount > account.balance:
            raise forms.ValidationError(
                f'You have {account.balance} $ in your account. '
                f'You can not transfer more than your account balance.'
            )
        return amount