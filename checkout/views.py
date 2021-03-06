from django.shortcuts import render, redirect, reverse, get_object_or_404, HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.conf import settings

from .models import Order, OrderLineItem
from .forms import OrderForm
from courses.models import Course
from bag.contexts import bag_contents

import stripe
import json


# Create your views here.
@require_POST
def cache_checkout_data(request):
    try:
        pid = request.POST.get('client_secret').split('_secret')[0]
        stripe.api_key = settings.STRIPE_SECRET_KEY
        stripe.PaymentIntent.modify(pid, metadata={
            'bag': json.dumps(request.session.get('bag', {})),
            'save_info': request.POST.get('save_info'),
            'username': request.user,
        })
        return HttpResponse(status=200)
    except Exception as e:
        messages.error(request, 'Beklager men din betaling gikk ikke\
            igjennom for øyeblikket, vennligst prøv igjen snart')
        return HttpResponse(content=e, status=400)


def checkout(request):
    """ A view to render the checkout form """
    stripe_public_key = settings.STRIPE_PUBLIC_KEY
    stripe_secret_key = settings.STRIPE_SECRET_KEY

    if request.method == 'POST':
        bag = request.session.get('bag', {})

        form_data = {
            'full_name': request.POST['full_name'],
            'email': request.POST['email'],
            'phone_number': request.POST['phone_number'],
        }
        order_form = OrderForm(form_data)
        if order_form.is_valid():
            order = order_form.save(commit=False)
            pid = request.POST.get('client_secret').split('_secret')[0]
            order.stripe_pid = pid
            order.original_bag = json.dumps(bag)
            order.save()
            for item_id, item_data in bag.items():
                try:
                    course = Course.objects.get(id=item_id)
                    if isinstance(item_data, int):
                        order_line_item = OrderLineItem(
                            order=order,
                            course=course,
                            quantity=item_data,
                        )
                        order_line_item.save()
                    else:
                        for quantity in item_data['quantity'].items():
                            order_line_item = OrderLineItem(
                                order=order,
                                course=course,
                                quantity=quantity,
                            )
                            order_line_item.save()
                except Course.DoesNotExist:
                    messages.error(request, (
                        "Ett av kursene i handlekurven din er ikke"
                        "tilgjengelig for øyeblikket. Vennligst"
                        "kontakt meg for mer informasjon")
                    )
                    order.delete()
                    return redirect(reverse('view_bag'))

            request.session['save_info'] = 'save-info' in request.POST
            return redirect(reverse('checkout_success',
                            args=[order.order_number]))
        else:
            messages.error(request, 'There was an error with your form. \
                Please double check your information.')
    else:
        bag = request.session.get('bag', {})
        if not bag:
            messages.error(request, "Du har ingenting i handlekurven!")
            return redirect(reverse('courses'))
        else:
            current_bag = bag_contents(request)
            total = current_bag['grand_total']
            stripe_total = round(total * 100)
            stripe.api_key = stripe_secret_key
            intent = stripe.PaymentIntent.create(
                amount=stripe_total,
                currency=settings.STRIPE_CURRENCY,
            )

            order_form = OrderForm()

        if not stripe_public_key:
            messages.warning(request, "Stripe public key is missing.")

        template = 'checkout/checkout.html'
        context = {
            'order_form': order_form,
            'stripe_public_key': stripe_public_key,
            'client_secret': intent.client_secret,
        }

        return render(request, template, context)


def checkout_success(request, order_number):
    """
    Successful checkouts
    """
    save_info = request.session.get('save_info')
    order = get_object_or_404(Order, order_number=order_number)
    messages.success(request, f'Din på melding til kurset: \
        {{ course.name }} er fullført! Ditt ordrenummer er: \
        og det er sendt en e-post til {order.email}. med din \
        bestilling. Takk som ønsker å benytte deg av min \
        tjenester')

    if 'bag' in request.session:
        del request.session['bag']

    template = 'checkout/checkout_success.html'
    context = {
        'order': order,
    }

    return render(request, template, context)
