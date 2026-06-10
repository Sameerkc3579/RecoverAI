content = open('d:/RecoveryAgent/static/css/app_v2.css', 'r', encoding='utf-8').read()

# Check transition presence in .card block
card_idx = content.find('.card {')
card_block = content[card_idx:card_idx+300]
print("transition in .card:", "transition" in card_block)
print("PREMIUM LIFT count:", content.count("PREMIUM LIFT"))
print("file size:", len(content))
