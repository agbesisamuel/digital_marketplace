from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from books.models import Book
from .models import Order, OrderItem, Payment


import stripe
import string
import  random

stripe.api_key = settings.STRIPE_SECRET_KEY

# anonymous function that creates a order reference code
def create_ref_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=15))


@login_required
def add_to_cart(request, book_slug):
    book = get_object_or_404(Book, slug=book_slug) #get a specific book item
    order_item, created = OrderItem.objects.get_or_create(book=book) # create a new book Order item 

    # here we create an order or get the order if it already exist
    # user=request.user check if an order exist for the user
    # 'created' is added when we use get_or_create method
    order, created = Order.objects.get_or_create(
        user=request.user, is_ordered=False)
    order.items.add(order_item)
    order.save()
    messages.info(request, "Item sucessfully added to cart")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))

@login_required
def remove_from_cart(request, book_slug):
    book = get_object_or_404(Book, slug=book_slug) #get a specific book item
    order_item = get_object_or_404(OrderItem, book=book) # create a new book Order item 
    order = Order.objects.get(user=request.user, is_ordered=False)
    order.items.remove(order_item)
    order.save()
    messages.info(request, "Item sucessfully removed from cart")
    return HttpResponseRedirect(request.META.get("HTTP_REFERER"))


#Order summary function
@login_required
def order_view(request):
    order = get_object_or_404(Order, user=request.user, is_ordered=False)
    context = {
        'order': order
    }
    return render(request, "order_summary.html", context)

    # order_qs = Order.objects.filter(user=request.user, is_ordered=False)
    # if order_qs.exists():
    #     context = {
    #         'order': order_qs[0]
    #     }
    #     return render(request, "order_summary.html", context)
    # raise Http404()


@login_required
def checkout(request):
    order_qs = Order.objects.filter(user=request.user, is_ordered=False)
    if order_qs.exists():
        order = order_qs[0]
    else:
        return Http404


    if request.method == 'POST':

        # Error handling

        try:
             # complete order (ref code and set is_ordered = True)
            order.ref_code = create_ref_code()
        
            # create a stripe charge
            token = request.POST.get('stripeToken')
            charge = stripe.Charge.create(
            amount=int(order.get_total() * 100), # amount is in cents
            currency="usd",
            source=token,
            description= f"Charge for { request.user.username }",
            )

            # create our payment object and link to the order
            payment = Payment()
            payment.order = order
            payment.stripe_charge_id = charge.id
            payment.total_amount = order.get_total()
            payment.save()

            # add the book to users book list
            # get all the books ordered by user
            books = [item.book for item in order.items.all()] 
            for book in books:
                request.user.userlibrary.books.add(book)
            
            order.is_ordered = True
            order.save()

            # redirect to the users profile
            messages.success(request, "Your order was successful!")
            return redirect("/account/profile/")

        # you may also send your self a message to keep tract of these errors
        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            messages.error(request, "There was a card errord")
            return redirect(reverse("cart:checkout"))
        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.error(request, "There was a rate limit error on Stripe")
            return redirect(reverse("cart:checkout"))
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.error(request, "Invalid parameter was supplied to stripe")
            return redirect(reverse("cart:checkout"))
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.error(request, "Invalid Stripe API Keys")
            return redirect(reverse("cart:checkout"))
        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.error(request, "There was a network error. Please try again")
            return redirect(reverse("cart:checkout"))
        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.error(request, "There was an error. Please try again")
            return redirect(reverse("cart:checkout"))
        except Exception as e:
            # Something else happened, completely unrelated to Stripe
            messages.error(request, "There was a serious error. We are working to resolve the issue")
            return redirect(reverse("cart:checkout"))

       
    context ={
        'order':order
    }
    return render(request, "checkout.html", context)