"""Verify the May bank movements already represented by existing journals."""
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json


def signature(snapshot):
    normalized = dict(snapshot)
    normalized.pop("source_rows", None)
    normalized["lines"] = sorted(
        (
            line["coa"],
            format(Decimal(str(line["debit"])), ".2f"),
            format(Decimal(str(line["credit"])), ".2f"),
            line["location_id"],
            line["description"],
        )
        for line in snapshot["lines"]
    )
    return sha256(json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def verify_entries(entries, unit_id, drafts, remaining, control):
    by_id = {entry.id: entry for entry in entries}
    by_row = {int(row[0]): row for row in drafts}
    covered_net = Counter()
    associations = {}
    for row_number, expected in EXPECTED.items():
        entry = by_id.get(expected["id"])
        if entry is None or entry.business_unit_id != unit_id:
            raise ValueError(f"Existing Catering journal missing for row {row_number}")
        snapshot = {
            "id": entry.id, "journal": entry.journal_number,
            "date": str(entry.posting_date), "status": entry.status,
            "source_type": entry.source_type, "reference_type": entry.reference_type,
            "reference_id": entry.reference_id, "document": entry.document_number,
            "external_reference": entry.external_reference, "description": entry.description,
            "lines": [{
                "coa": line.account.account_number,
                "debit": str(line.debit), "credit": str(line.credit),
                "location_id": line.location_id, "description": line.description,
            } for line in entry.lines],
        }
        if signature(snapshot) != expected["signature"]:
            raise ValueError(f"Existing journal changed: {expected['journal']}")
        row = by_row[row_number]
        bank_lines = [line for line in snapshot["lines"] if line["coa"].startswith("100-110-")]
        if (str(row[1]) != snapshot["date"] or len(bank_lines) != 1
                or bank_lines[0]["coa"] != row[3]
                or Decimal(bank_lines[0]["debit"]) != row[4]
                or Decimal(bank_lines[0]["credit"]) != row[5]):
            raise ValueError(f"Source bank movement changed at row {row_number}")
        if sum(Decimal(line["debit"]) - Decimal(line["credit"]) for line in snapshot["lines"]):
            raise ValueError(f"Existing journal is unbalanced: {entry.journal_number}")
        covered_net[row[3]] += row[4] - row[5]
        associations[str(row_number)] = entry.journal_number

    new_net = Counter()
    for _, _, _, bank, debit, credit, contra, _ in remaining:
        new_net[bank] += debit - credit
        if contra in control:
            new_net[contra] += credit - debit
    if any(new_net[code] + covered_net[code] != item["net_seed"] for code, item in control.items()):
        raise ValueError("Combined existing and new bank movements do not match the full source plan")
    return {
        "retained_journals": len(associations),
        "source_rows_to_existing_journals": associations,
        "retained_bank_net": dict(covered_net),
    }


def verify_database(db, unit_id, drafts, remaining, control):
    from app.models.journal_entry import JournalEntry

    entries = db.query(JournalEntry).filter(
        JournalEntry.id.in_([item["id"] for item in EXPECTED.values()])
    ).all()
    return verify_entries(entries, unit_id, drafts, remaining, control)


EXPECTED = {445: {'id': 15328,
       'journal': 'MAN-202611-009628',
       'signature': 'de119ba0ff98ef57dc6c7925e571368585377fe6a57ab46d2bd5043b1ac7455d'},
 647: {'id': 15244,
       'journal': 'PAY-202611-0611',
       'signature': '80ca24f3c90a00e201936ae3a8eeeb446b1eb41542498596e80a7c09e1dee0d9'},
 649: {'id': 15317,
       'journal': 'PAY-202611-0684',
       'signature': 'c36f98c5b99b6a847cf0b49747fc4f3983f699f94b3709fd7cc575d27b86704a'},
 651: {'id': 15247,
       'journal': 'PAY-202611-0614',
       'signature': '80a626979ca582d166cfda423fea5389ff826a4ac169137dd6e56dc5575c4262'},
 652: {'id': 15236,
       'journal': 'PAY-202611-0603',
       'signature': 'cac8843ad0af15de9d21d723e5ec152b6990c65f7435f2d7d09c2e5019d193b6'},
 653: {'id': 15215,
       'journal': 'PAY-202611-0583',
       'signature': '2e71e0355b809d4e73c0843791a22c2085874a4131850bf889863d063c1f7613'},
 654: {'id': 15212,
       'journal': 'PAY-202611-0580',
       'signature': '4b4a4e5f7ea4b74b4c700115f6a1316c701ac971ba1103ea743ddbcd700c1a33'},
 655: {'id': 15221,
       'journal': 'PAY-202611-0589',
       'signature': '6ee3420090bf1bb6d9ae603ebcaee656083f22758550d5d1d910c1ca923fddaa'},
 656: {'id': 15218,
       'journal': 'PAY-202611-0586',
       'signature': 'e0e4222b0c1a3a8893b7d0d2bb403575e84b92e383b0a4d3936b30e11ee56e43'},
 657: {'id': 15209,
       'journal': 'PAY-202611-0577',
       'signature': 'c86366a95610e2d9ee8fa71f1a21dda50f9fb8a4cbaedaeaf9f06424c477c2be'},
 658: {'id': 15230,
       'journal': 'PAY-202611-0598',
       'signature': 'b281597774e7cd58c5e224e7850690905b3114373f1c661b44c5a4347602d67b'},
 659: {'id': 15225,
       'journal': 'PAY-202611-0593',
       'signature': '6153b7e820cd15525e427cabdd3abe591bdb69f9b58133af6b02109ed39fdf11'},
 660: {'id': 15239,
       'journal': 'PAY-202611-0606',
       'signature': 'f58d4c393a2f64e731313d247921ca6273cd46d90a9adcb05428f335e80e9b33'},
 661: {'id': 15200,
       'journal': 'PAY-202611-0568',
       'signature': 'b104792f0e88487af139167cb75d5155bdcaea959a5de98f2ea48da542f8b90b'},
 662: {'id': 15191,
       'journal': 'PAY-202611-0559',
       'signature': '11557a596ba2559f43d5ea431b8ebb684dbb5411a43333ccaa93bb46b81c5cbf'},
 663: {'id': 15194,
       'journal': 'PAY-202611-0562',
       'signature': '30dc2f5c724c2f261ce6cc5314514e440d4f8491387207c9479a2c77b272f193'},
 664: {'id': 15188,
       'journal': 'PAY-202611-0556',
       'signature': '71cd6df8537d84b946d0233cc91b761c2b1885cc480f62b10c9974c2a0b79a4d'},
 665: {'id': 15206,
       'journal': 'PAY-202611-0574',
       'signature': '53aa69e04a0a329a635b24d0ce2bbf38ae20aa048ebc51335416fcafa4c73df2'},
 666: {'id': 15185,
       'journal': 'PAY-202611-0553',
       'signature': 'd1dba5021fce30de0b168d545163b2e6fdd06547c89d94c16faf7a7e93525297'},
 704: {'id': 15162,
       'journal': 'MAN-202611-009616',
       'signature': 'e548970b0e4ffd7d9164d9932c2f6362e7de935256bbc0d429e11637cf9560f9'},
 705: {'id': 15152,
       'journal': 'MAN-202611-009606',
       'signature': '23fef7718236e72b22e304503d519fb58cf7ecf7084a1a60081a436f5f994ea7'},
 706: {'id': 15153,
       'journal': 'MAN-202611-009607',
       'signature': '958f6ae3d1f34d77c9eefb4aae70d6981fdb531a55a84a2c2037dc42fa49cf1c'},
 708: {'id': 15158,
       'journal': 'MAN-202611-009612',
       'signature': '1a60f50882c4a21153574af58ec3ef8437eff4d01eeb4d4d8d0648c260dbe99b'},
 709: {'id': 15156,
       'journal': 'MAN-202611-009610',
       'signature': '998884d75e734a009b5386003ad83586783092a437cdb38326a4b78a5b49c946'},
 710: {'id': 15159,
       'journal': 'MAN-202611-009613',
       'signature': '268db5041545eace0657112e1212a6fb2695dae6ea61fc38edc542c417c6358f'},
 711: {'id': 15157,
       'journal': 'MAN-202611-009611',
       'signature': 'a36620915d1945118d332205668be1e09370c05d9bbc7845ee5e0361b3c7b4e5'},
 712: {'id': 15182,
       'journal': 'PAY-202611-0550',
       'signature': '14d4a8e7090333b0947e56764f9f6481c250878951cb984c3cad31724b63fc6f'},
 718: {'id': 15154,
       'journal': 'MAN-202611-009608',
       'signature': '23febc6076c3cba29bb26b7fa70e91fb809e600ee237bde0cae31d67676a2072'},
 723: {'id': 15163,
       'journal': 'MAN-202611-009617',
       'signature': 'ea7e5f6dbc38a75b054508e0921c047370c01e9c6f9bbb09993bea07b4518fdc'},
 724: {'id': 15164,
       'journal': 'MAN-202611-009618',
       'signature': '16e2eaddfaf329d427bf9035f443183556ce4dae8d51e959569e39b37b1766dd'},
 725: {'id': 15161,
       'journal': 'MAN-202611-009615',
       'signature': '3b03afff85a512973d95a469c99b937685c185be53d08bd58341bf6536f2a883'},
 726: {'id': 15160,
       'journal': 'MAN-202611-009614',
       'signature': '247e5d7c5575d869b40842a52a18074583fdb9f4b15e85df07ff3400d5293405'},
 727: {'id': 15155,
       'journal': 'MAN-202611-009609',
       'signature': '87aa5a8196d076a7a51aabd60047c9dc953b7cca25ac52ac886fb061ad83bde2'},
 729: {'id': 15168,
       'journal': 'MAN-202611-009622',
       'signature': '2fb35c2ca814757a4129002e659589644c16adea26c88e4603f76c3c2cd1e6b3'},
 730: {'id': 15169,
       'journal': 'MAN-202611-009623',
       'signature': 'cb6baf05e707895cb9a88b88c4f966f1514d9b337e363e241f7618f1ecc0ce17'},
 731: {'id': 15166,
       'journal': 'MAN-202611-009620',
       'signature': '3791702a1be68ad856ec864b38e123db846e6fff246b489832f51909ceec1ea0'},
 732: {'id': 15167,
       'journal': 'MAN-202611-009621',
       'signature': 'c1eac8f33517594f488f204fb0cfbb4d98d4b5b41440dafe17c056617d46ab16'},
 733: {'id': 15165,
       'journal': 'MAN-202611-009619',
       'signature': '0b269754c234308999f5f7c9995bedce3bae8eb0e98cf03965a722f1fbbc5d2a'},
 734: {'id': 15179,
       'journal': 'PAY-202611-0547',
       'signature': 'b1c53f15ac267a1570f166f4805667ca06f72aa2bf564fcbefcd6e30b28e6bc3'},
 735: {'id': 15174,
       'journal': 'MAN-202611-009625',
       'signature': 'c8cf61ae0a8964ec227ed625e3e9bd0a43d4c6cddd7a5bfec289be9c5f899a0a'},
 742: {'id': 15173,
       'journal': 'PAY-202611-0542',
       'signature': '28807950bc55e60e25363cbc6f120de2d3254c7257a65c738923121d71e5672d'},
 790: {'id': 15197,
       'journal': 'PAY-202611-0565',
       'signature': 'b7d427d787d218948738054434087044ec1e4d747037bff97d419851e66b876a'},
 791: {'id': 14985,
       'journal': 'MAN-202611-009473',
       'signature': '6395ccf97b2b4869d8bdb898c9d6297a99f920f3e1d36303c3655ef00d53b886'},
 800: {'id': 15203,
       'journal': 'PAY-202611-0571',
       'signature': 'a47125738c1ea17c96c7f17a7fffba20d0864c5e1ab65db0a754bce3b1d9d98a'},
 809: {'id': 13947,
       'journal': 'MAN-202611-008467',
       'signature': '19f216649a25a626e77bed31366f16dc173f107a11f7b438af134c92a448a4d6'},
 810: {'id': 13940,
       'journal': 'MAN-202611-008466',
       'signature': '2538bd5fbaae461d8c51455399bf3f1247bf928594adfb3fb5b605a5153b85b8'},
 812: {'id': 13925,
       'journal': 'MAN-202611-008456',
       'signature': '2a83444237f7a54e0b787c5eaf56d6386e20cef1910b4295d30eca4ce4120e06'},
 813: {'id': 13924,
       'journal': 'MAN-202611-008455',
       'signature': '52ebf23088634a35cce2456c9acd509d4be03c68da9edb4038e06571ddd60769'},
 1138: {'id': 13909,
        'journal': 'MAN-202611-008454',
        'signature': 'df6006a254caf418c77bd35ea0f5bdf74fc10343aec7e93fb31289c5cb2c3914'},
 1140: {'id': 13908,
        'journal': 'MAN-202611-008453',
        'signature': '9d061e6ad081d95f672ab05de9364150bcbea8e923fe1bef730ab5fedca391a1'},
 1198: {'id': 13905,
        'journal': 'MAN-202611-008450',
        'signature': '66c4f6af5f18d3913783a6479dd3e95ef961609f028fb11f78030d1aa9f8f490'},
 1199: {'id': 13907,
        'journal': 'MAN-202611-008452',
        'signature': '7bfeb3729f3ebe943e9844ed7411fa7dbe5d9595f4b463d972961ae06454f9fb'},
 1200: {'id': 13906,
        'journal': 'MAN-202611-008451',
        'signature': 'ab681d75e4b5b77f4ad1e764e64c865fa51b0ef6b314d0b896c29d28e6ac2bd7'},
 1201: {'id': 13904,
        'journal': 'MAN-202611-008449',
        'signature': '75be4fd40c6e35f1cac0b3c337145da3dd342834c3d8a2b13a82351a368af1e0'}}
