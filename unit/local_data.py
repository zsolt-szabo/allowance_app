class test_data:
    user1 = {
        "firstname": "person1",
        "email": "person1@mail.com",
        "pw_hash": "monstertruck"
    }

    user2 = {
        "firstname": "person2",
        "email": "person2@mail.com",
        "pw_hash": "monstertruck"
    }

    user1_kid1 = {
        "firstname": "whipper",
        "animal1": "rabbit",
        "animal2": "rabbit",
        "animal3": "goose",
        "animal4": "goose",
        "parent_id": 1,
        "pw": "snapper",
        "acct1_name": "Spending",
        "acct2_name": "Savings",
        "acct1_used": 1,
        "acct2_used": 1,
        "location1_name": "Mom/Dad's wallet",
        "location2_name": "Gift Card From Grandma",
        "location1_used": 1,
        "location2_used": 1,
    }

    user2_kid2 = {
        "firstname": "larry",
        "animal1": "tiger",
        "animal2": "tiger",
        "animal3": "goose",
        "animal4": "goose",
        "parent_id": 2,
        "pw": "snapper",
        "acct1_name": "Spending",
        "acct2_name": "Savings",
        "acct1_used": 1,
        "acct2_used": 1,
        "location1_name": "Mom/Dad's wallet",
        "location2_name": "Gift Card From Uncle Bob",
        "location1_used": 1,
        "location2_used": 1,
    }

    kid1_allow_good = {
        "kid_id": 1,
        "nickname": "kid1 good allowance",
        "acct1_perc": 80,
        "acct2_perc": 20,
        "location1_perc": 100,
        "amount": 3,
        "payout_days": [1, 10, 20]
    }

    kid2_allow_good = {
        "kid_id": 2,
        "nickname": "kid2 good allowance",
        "acct1_perc": 30,
        "acct2_perc": 70,
        "location1_perc": 95,
        "location2_perc": 5,
        "amount": 4,
        "payout_days": [2, 11, 21]
    }

    kid1_allow_bad = {
        "kid_id": 1,
        "nickname": "kid1 BAD allowance",
        "acct1_perc": 100,
        "location1_perc": 100,
        "amount": 3,
        "payout_days": [1, 10, 20]
     }
