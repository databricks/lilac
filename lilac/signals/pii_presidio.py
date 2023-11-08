import presidio_analyzer

PII_CATEGORIES = [

]


CREDIT_CARD	A credit card number is between 12 to 19 digits. https://en.wikipedia.org/wiki/Payment_card_number	Pattern match and checksum
CRYPTO	A Crypto wallet number. Currently only Bitcoin address is supported	Pattern match, context and checksum
DATE_TIME	Absolute or relative dates or periods or times smaller than a day.	Pattern match and context
EMAIL_ADDRESS	An email address identifies an email box to which email messages are delivered	Pattern match, context and RFC-822 validation
IBAN_CODE	The International Bank Account Number (IBAN) is an internationally agreed system of identifying bank accounts across national borders to facilitate the communication and processing of cross border transactions with a reduced risk of transcription errors.	Pattern match, context and checksum
IP_ADDRESS	An Internet Protocol (IP) address (either IPv4 or IPv6).	Pattern match, context and checksum
NRP	A person’s Nationality, religious or political group.	Custom logic and context
LOCATION	Name of politically or geographically defined location (cities, provinces, countries, international regions, bodies of water, mountains	Custom logic and context
PERSON	A full person name, which can include first names, middle names or initials, and last names.	Custom logic and context
PHONE_NUMBER	A telephone number	Custom logic, pattern match and context
MEDICAL_LICENSE	Common medical license numbers.	Pattern match, context and checksum
URL
