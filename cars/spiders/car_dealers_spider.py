import scrapy

class CarDealersSpider(scrapy.Spider):
    # This name is used for running the spider
    name = "car_dealers"

    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36'
    }
    def start_requests(self):
        # This is a list of zip codes that we would like to scrape
        zip_codes = ['77001']


        for zip_code in zip_codes:
            url = 'https://www.cars.com/dealers/buy/' + zip_code + \
                '/?rd=30&sortBy=DISTANCE&order=ASC&perPage=1000'
            yield scrapy.Request(url=url, callback=self.parse_listings_page, headers=self.headers)

    def parse_listings_page(self, response):
        # First of all we need to get each individual dealer section
        dealers = response.xpath('//*[@class="dealer-result"]')

        for dealer in dealers:
            # For every dealer we extract the name
            name = dealer.xpath('.//h2[contains(@class, "result-name")]/text()').extract_first().strip()
            # There is no specific value for ratings, but no problem!
            # We can get the svg star elements and use their class to
            # understand the star rating.
            stars = dealer.xpath('.//div[@itemprop="aggregateRating"]//*[contains(@class, "icon-image")]/@class').extract()
            star_rating = 0
            
            for star in stars:
                # Filled stars = 1 star
                # Half star = 0.5 star
                # By adding these values we end up with a star rating from 0 to 5.
                if 'filled' in star:
                    star_rating += 1
                elif 'half' in star:
                    star_rating += 0.5

            # The address is split into multiple spans with a common parent
            # We want all the spans, except for the span that says "10 miles away"
            address = dealer.xpath('.//address/div[1]/span[not(@class="distance")]/text()').extract()
            # We clean up each span with a list comprehension
            address = [a.replace("\n", "").strip() for a in address]
            # And once everything is cleaned we join all the parts (street address, city & zip code)
            address = ', '.join(address)

            # This section's text is "50 reviews", "No reviews" or "0 recent"
            # The following edits take care of all the scenarios by replacing 
            # all the string values and keeping only the numeric value that we want
            # to extract
            review_count = dealer.xpath('.//a[@class="reviews-link"]/text()').extract_first()
            review_count = review_count.replace(" reviews", "").replace(" review", "").replace("\n", "").strip()
            review_count = review_count.replace(" recent", "")
            review_count = 0 if review_count == 'No' else int(review_count)
            
            # We create a new object that we will pass on to the next request
            dealer_obj = {
                'name': name,
                'rating': star_rating,
                'number_of_reviews': review_count,
                'address': address,
                'used_phone': '',
                'new_phone': '',
                'service_phone': ''
            }

            # We pare the phone numbers table toe extract all phone numbers
            phone_numbers = dealer.xpath('.//table[@class="sales-phone-numbers"]/tr')
            for number in phone_numbers:
                phone_type = number.xpath('.//td[@class="phone-number-label"]/text()').extract_first().strip()
                number_xpath = './/td[@class="phone-number-value"]/a[@class="clickable-phone-number"]/text()'
                phone_number = number.xpath(number_xpath).extract_first()

                if not phone_number:
                    continue

                phone_number = phone_number.replace("\n", "").strip()

                if phone_type == 'New':
                    dealer_obj['new_phone'] = phone_number
                elif phone_type == 'Used':
                    dealer_obj['used_phone'] = phone_number
                elif phone_type == 'Service':
                    dealer_obj['service_phone'] = phone_number

            # As a final step, we get the URL for the specific page of the dealer
            dealer_url = dealer.xpath('.//a[@data-linkname="dealer-name"]/@href').extract_first()
            dealer_url = 'https://www.cars.com' + dealer_url

            # We pass the new URL to a new request
            # IMPORTANT: We pass the dealer as meta so we can keep all the info we
            # already gathered
            yield scrapy.Request(url=dealer_url, headers=self.headers,
                callback=self.parse_dealer_page, meta={'dealer': dealer_obj})


    def parse_dealer_page(self, response):
        # Here we get the existing info from the meta param
        dealer = response.meta['dealer']
        
        # The listing URL on Cars.com is the url used in the request
        dealer['listing_url'] = response.request.url

        # We get the dealer's website
        website = response.xpath('//a[@class="dealer-update-website-link"]/@href').extract_first()
        dealer['website'] = website

        # We get the used & new vehcile counts from props in an element
        # that is used.
        vehicle_count_new = response.xpath('//dpp-update-inventory-link/@new-count').extract_first()
        vehicle_count_used = response.xpath('//dpp-update-inventory-link/@used-count').extract_first()

        # These values may be none. We replace None values with 0 to avoid issues
        vehicle_count_new = vehicle_count_new if vehicle_count_new else 0
        vehicle_count_used = vehicle_count_used if vehicle_count_used else 0

        vehicle_count = int(vehicle_count_used) + int(vehicle_count_new)

        # We define all the vehice counts
        dealer['vehicle_count_total'] = vehicle_count
        dealer['vehicle_count_used'] = vehicle_count_used
        dealer['vehicle_count_new'] = vehicle_count_new

        # And finally we yield the row to be stored in JSON, CSV or Database
        # depending on our needs
        yield dealer