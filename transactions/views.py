from django.shortcuts import render
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView,ListView
from transactions.models import Transaction
from .forms import DepositForm,WithdrawForm,LoanRequestForm,TransferBalanceForm
from .constants import DEPOSIT,WITHDRAWAL,LOAN,LOAN_PAID,TRANSFER_BALANCE
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import HttpResponse
from datetime import datetime
from django.db.models import Sum
from django.views import View
from django.shortcuts import get_object_or_404,redirect
from accounts.models import UserBankAccount
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
# Create your views here.


def send_transaction_email(user,amount,subject,template):
        message = render_to_string(template,{
            'user':user,
            'amount': amount,
        })
        send_email = EmailMultiAlternatives(subject,'',to=[user.email])
        send_email.attach_alternative(message,"text/html")
        send_email.send()


class TransactionCreateMixin(LoginRequiredMixin,CreateView):
    template_name = 'transactions/transaction_form.html'
    model = Transaction
    title = ''
    success_url = reverse_lazy('transaction_report')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({
            'account': self.request.user.account
        })
        return kwargs

    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title
        })
        return context

class DepositMoneyView(TransactionCreateMixin):
    form_class = DepositForm
    title = 'Deposit'

    def get_initial(self):
        initial = {'transaction_type':DEPOSIT}
        return initial

    def form_valid(self,form):
        amount = form.cleaned_data.get('amount')
        account = self.request.user.account
        # if not account.initial_deposit_date:
        #     now = timezone.now()
        #     account.initial_deposit_date = now
        account.balance += amount
        account.save(
            update_fields = [
                'balance'
            ]
        )
        send_transaction_email(self.request.user,amount,"Deposit Message","transactions/deposit_email.html")
        messages.success(
            self.request,
            f'{"{:,.2f}".format(float(amount))}$ was deposited to your account successfully'
        )
        return super().form_valid(form)

class WithdrawMoneyView(TransactionCreateMixin):

    form_class = WithdrawForm
    title = 'Withdraw Money'

    def get_initial(self):
        initial = {'transaction_type':WITHDRAWAL}
        return initial
    
    def form_valid(self,form):
        amount = form.cleaned_data.get('amount')

        self.request.user.account.balance -= form.cleaned_data.get('amount')
        # balance = 300
        # amount = 5000
        self.request.user.account.save(update_fields=['balance'])

        messages.success(
            self.request,
            f'Successfully withdrawn {"{:,.2f}".format(float(amount))}$ form your account'
        )
        send_transaction_email(self.request.user,amount,"Withdrawal Message","transactions/withdrawal_email.html")

        return super().form_valid(form)
    

class LoanRequestView(TransactionCreateMixin):
    form_class = LoanRequestForm
    title = 'Request For Loan'

    def get_initial(self):
        initial = {'transaction_type':LOAN}
        return initial 

    def form_valid(self,form):
        amount = form.cleaned_data.get('amount')
        current_loan_count = Transaction.objects.filter(
            account=self.request.user.account,transaction_type=3,loan_approve=True).count()
        if current_loan_count >= 3:
            return HttpResponse("You have cross the loan limits")    
        messages.success(
            self.request,
            f'Loan request for {"{:,.2f}".format(float(amount))}$ submitted successfully'
        )
        send_transaction_email(self.request.user,amount,"Loan Request Message","transactions/loan_email.html")
        return super().form_valid(form)

class TransactionReportView(LoginRequiredMixin,ListView):
    template_name = 'transactions/transaction_report.html'
    model = Transaction
    balance = 0 # filter korar pore ba age amar total balance ke show korbe
    def get_queryset(self):
        queryset = super().get_queryset().filter(
            account = self.request.user.account
        )
        start_date_str = self.request.GET.get('start_date')
        end_date_str = self.request.GET.get('end_date')
        
        if start_date_str and end_date_str:
            start_date = datetime.strptime(start_date_str,'%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str,'%Y-%m-%d').date()

            queryset = queryset.filter(timestamp__date__gte=start_date,timestamp__date__lte=end_date)
            self.balance = Transaction.objects.filter(
                timestamp__date__gte=start_date,timestamp__date__lte=end_date
            ).aggregate(Sum('amount'))['amount__sum']
        else:
            self.balance = self.request.user.account.balance
        return queryset.distinct() # unique queryset hote hobe
    
    def get_context_data(self,**kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'account':self.request.user.account
        })
        return context


class PayLoanView(LoginRequiredMixin,View):
    def get(self,request,loan_id):
        loan = get_object_or_404(Transaction,id=loan_id)
        if loan.loan_approve:
            user_account = loan.account
                # Reduce the loan amount from the user's balance
                # 5000, 500 + 5000 = 5500
                # balance = 3000, loan = 5000
            if loan.amount < user_account.balance:
                user_account.balance -= loan.amount
                loan.balance_after_transaction = user_account.balance
                user_account.save()
                loan.loan_approve = True
                loan.transaction_type = LOAN_PAID
                loan.save()
                return redirect('loan_list')
            else:
                messages.error(
                    self.request,
                    f'Loan amount is greater than available balance'
                )
        return redirect('loan_list')


class LoanListView(LoginRequiredMixin,ListView):
    model = Transaction
    template_name = 'transactions/loan_request.html'
    context_object_name = 'loans' # loan list ta ei loans context er moddhe thakbe

    def get_queryset(self):
        user_account = self.request.user.account
        queryset = Transaction.objects.filter(account=user_account,transaction_type=3)
        return queryset


class TransferBalanceView(TransactionCreateMixin):
    form_class = TransferBalanceForm
    title = 'Transfer Balance'

    def get_initial(self):
        initial = {'transaction_type': TRANSFER_BALANCE}
        return initial

    def form_valid(self,form):
        amount = form.cleaned_data.get('amount')
        account_number = form.cleaned_data.get('account_number')
        receiver_account = UserBankAccount.objects.get(account_no=account_number)
        if receiver_account is not None:
            self.request.user.account.balance -= amount
            self.request.user.account.save(update_fields=['balance'])
            receiver_account.balance += amount
            receiver_account.save(update_fields=['balance'])

            messages.success(self.request, f'Successfully transferred {"{:,.2f}".format(float(amount))}$ form your account')
            send_transaction_email(self.request.user,amount,"Transferred amount message","transactions/balance_transfer_email.html")
            send_transaction_email(receiver_account.user,amount,"Received amount message","transactions/balance_received_email.html")
        else:
            messages.error(self.request, f'This account does not exist')
        return super().form_valid(form)