Trade-offs
1. Python csv module instead of pandas

I used csv.DictReader instead of pandas. Pandas would provide convenient dataframe operations, but it would be a large dependency for a 60-row file and could automatically infer types in ways that hide malformed input. The standard library keeps installation lightweight and gives the program explicit control over every input value. The trade-off is that row iteration and validation require more manual code.

2. Decimal instead of floating-point numbers

I used Decimal to parse monetary amounts instead of float. Floating-point values can introduce precision errors when converting dollars into cents, while Decimal represents the supplied decimal values accurately. This adds a little extra code and requires handling InvalidOperation, but it makes the monetary conversion more reliable.

3. Separate normalization functions instead of one large transformation

Date, amount, currency, and merchant normalization are implemented as separate functions, while normalize_rows coordinates the overall row processing. This makes each rule easier to test and keeps changes to one field from affecting unrelated fields. The trade-off is additional functions and some repeated function-call code compared with putting the entire transformation into one loop.