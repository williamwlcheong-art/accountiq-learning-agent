# AccountIQ website: design brief

Date: 2026-09-16
For: generating alternative designs for the public marketing site.

This brief is self-contained. Everything needed to design the site is in it,
including the finished copy.

## Why the current site reads as generic

Six specific causes, checked against the running site rather than guessed.

1. **No typeface was ever chosen.** Every heading and every paragraph resolves
   to `"Segoe UI", system-ui, sans-serif`. The site is rendering in whatever the
   visitor's operating system defaults to. This is the largest single cause and
   the cheapest to fix.
2. **The report never appears.** AccountIQ's whole product is a document, and
   there is not one image of that document anywhere on the site. Every section
   describes it in words instead.
3. **There is not a single number on a site about numbers.** The price, the
   turnaround, an example valuation and a multiple are all absent.
4. **Nobody is named.** The copy says a person reviews every report without
   saying who. That anonymous reviewer is the entire differentiator and reads
   like a factory inspection step.
5. **Two different navies.** The app uses `#1a2a40`, the marketing pages use
   `#1b1464`. A visitor crossing from the site into the product sees the brand
   change colour.
6. **Every section has the same shape.** Heading, then prose, on an alternating
   white and grey background. No cards, tables, figures, charts, photographs or
   rules. At 1440 pixels the hero text occupies the left half and the right half
   is empty.

## What the site is

A New Zealand business owner uploads their annual financial statements, answers
questions about the business, and receives an indicative business valuation
report as a PDF for one published fee. William Cheong, a chartered accountant,
reads every report before it is released.

It is explicitly not a certified valuation and not financial advice. For a
court, a formal dispute or a tax filing, the owner needs a registered valuer,
and the site says so plainly rather than burying it.

**Mode: persuade.** The visitor's success is deciding to buy. Design is doing
the selling here, not supporting a task.

## Who it is for

A New Zealand business owner, between roughly 45 and 65, turnover between
$500,000 and $10 million. They are not finance people. They own a
manufacturing business, a services firm, a few franchise sites.

They are here because something has already happened. A competitor has made an
approach. A shareholder wants out. The bank has asked for a number on a form. A
relationship has ended. They are not browsing.

They are cautious about uploading their financial statements to a website they
have not heard of, and that caution is the thing the design has to overcome.

Accountants and business brokers are a second audience, served by one page.

## The market the design has to position against

Prices read from the competitors' own pages on 2026-09-16.

| Who | Price (ex GST) | Turnaround |
|---|---|---|
| A business broker's appraisal | Free, and conflicted | Days |
| Bizstats comparable sales report | $60 | Instant |
| **AccountIQ** | **$1,200 (working assumption)** | **3 working days** |
| Bizval CA-compiled report | $2,250 to $5,200 | 7 to 21 working days |
| Fealty certified valuation | $4,900 to $9,900 | 3 to 8 weeks |

AccountIQ sits in a real gap: it reads the actual statements, which the $60
report does not, and it comes back in days rather than weeks.

**The fee is not yet decided.** $1,200 is a working assumption so the design has
a real number to lay out. Treat the figure as replaceable and the layout as not.

## What the design has to do

In order of how much each one matters.

1. **Show the report.** The single most persuasive asset is the thing being
   sold. Real pages, readable, not a blurred mockup behind a gradient.
2. **Show the price, high.** Three competitors publish theirs. A site that hides
   the number loses to the ones that do not.
3. **Show William.** A named chartered accountant reading the accounts is what a
   free calculator and an AI answer cannot copy. Photograph, name, credentials,
   near every mention of money.
4. **Answer "where do my financial statements go".** The upload is the moment of
   fear. The answer cannot be a link in the footer.
5. **Say who it is not for.** Disqualifying the court and tax cases raises trust
   with everyone else.

## Visual direction

### The constraint

It has to look like something a chartered accountant would put their name to,
and it has to be warmer than an accounting firm's website. Those firms look
expensive and unapproachable, which is the feeling this product exists to
undercut. Do not end up at another navy-and-white SaaS landing page, and do not
end up at a mid-tier advisory firm either.

### Three directions to explore

**A. The document.** The site is built like the report it sells. A real serif
for headings, generous margins, hairline rules, tabular figures, paper-white
rather than pure white. Report pages appear at scale as the main imagery. Feels
considered and permanent, the way a good professional document feels.

**B. The plain number.** Swiss discipline. A tight grid, near-monochrome with a
single accent, and large tabular numerals as the recurring visual motif. The
prices, the turnaround, the valuation ranges become the design rather than
sitting inside it. Feels precise and modern, and carries the price positioning
without arguing for it.

**C. The practice.** Warmer and photographic. William, a real desk, real New
Zealand business owners. Leads with the person instead of the document. Feels
local and human, and risks looking like an accounting firm if the photography is
not genuinely good.

**Recommended: A, with B's discipline about numbers.** The product is a document
and the positioning is credibility at a lower price, so the site should look
like the document and be unafraid of the figures. C works as a section inside A,
not as the whole site.

### Fixed brand constraints

- The AccountIQ wordmark stays.
- Pick one navy and use it in both the site and the product. `#1b1464` is more
  distinctive than `#1a2a40`; take one, drop the other.
- New Zealand English throughout.
- Accessible contrast, and a visible focus state on everything interactive.
- Works down to 320 pixels wide. The owner reading this on a phone in a car park
  between meetings is a real case.

### Typography

Choosing a typeface is the highest-value single change available. Whatever the
direction, headings and body text need to be a deliberate choice, and numbers
need tabular figures so columns line up.

## Assets needed from William

The design cannot be finished without these, and three of them are blocking.

- A photograph of William. Not a stock headshot.
- The full sample report as a PDF, on a made-up company, so its pages can be
  shown.
- His CA ANZ membership details and a short history: where he trained, where he
  practised, how long.
- The fee, and whether it includes GST.
- Three customers willing to be named with one sentence each.
- The real turnaround in working days.

---

# Page copy

Finished copy, ready to lay out. Square brackets mark something only William can
supply.

## Home

**Hero heading**
What is your business worth?

**Hero subheading**
Upload your last two to three years of financial statements, answer some
questions about the business, and get an indicative valuation report for $1,200.
A chartered accountant reads it before it reaches you.

**Primary button:** Start your valuation
**Secondary button:** Look at a full sample report first

**Under the buttons**
Indicative only. Not financial advice or a certified valuation.

**Price strip, immediately below the hero**

| | |
|---|---|
| $1,200 | One published fee, not a quote |
| 3 working days | From upload to finished report |
| Every report | Read by William Cheong CA before release |

**Section: Most owners ask because something has already happened**

You are thinking about selling.
Before you talk to a buyer or a broker, you want a number you can hold in your
head, and the reasoning behind it.

A shareholder wants out.
A partner is leaving, a family member is coming in, or a shareholder agreement
needs a starting figure everyone can see.

The bank has asked.
A lender or an investor wants to know what the business is worth, and they want
it written down.

**Section: What you actually get**

Twelve to sixteen pages on your business, not a template with your name at the
top.

The report normalises your earnings, which means adjusting for the salary you
pay yourself, the one-off costs, and the personal expenses running through the
business. It applies more than one valuation method and shows you where they
disagree. It names the things that move your number up or down: how much depends
on you personally, how concentrated your customers are, how much of your revenue
repeats.

Every assumption is on the page. When a buyer disagrees with your number, you can
see exactly which assumption they are arguing with.

**Button:** Look at a full sample report

**Section: William reads every report**

[Photograph]

William Cheong is a chartered accountant [CA ANZ member number, where he trained,
how long he has practised]. He opens the statements, checks the assumptions
against them, and holds the report back if something does not add up.

That is the part a free online calculator cannot do. A calculator takes a revenue
figure and a multiple and hands you a number. It has never seen your accounts.

**Section: How it compares**

| | Cost | Time | Reads your accounts |
|---|---|---|---|
| A broker's free appraisal | Free | Days | No, and they want your listing |
| A comparable sales report | About $60 | Instant | No |
| **AccountIQ** | **$1,200** | **3 working days** | **Yes** |
| A valuation from an accounting firm | $2,250 to $5,200 | 7 to 21 working days | Yes |
| A certified valuation | $4,900 to $9,900 | 3 to 8 weeks | Yes |

**Under the table**
If you need something a court, the IRD or a formal dispute will accept, you need
a certified valuer, and this is not that. For working out whether a conversation
is worth having, and on what terms, this is usually enough.

**Section: Your financial statements**

Your statements are stored [where], opened by [who], processed by
[which provider], and deleted after [how long].

**Link:** Read the full detail

**Final call to action**
Find out what your business may be worth
$1,200. Three working days. Read by a chartered accountant before you see it.

**Button:** Get started

## Pricing

**Heading**
What a business valuation costs in New Zealand

**Opening**
AccountIQ charges $1,200 [GST treatment] for an indicative valuation report,
published here rather than quoted after a phone call. Below is what everything
else costs, so you can see where that sits.

**How much should a business valuation cost?**

It depends entirely on what the number has to survive.

A broker will appraise your business free, because they want the listing. It is
a real opinion from someone who sells businesses for a living, and who has an
interest in the answer.

A comparable sales report costs around $60 and tells you what similar businesses
sold for. Useful, but it has never seen your accounts.

A report from an accounting firm runs $2,250 to $5,200 and takes seven to
twenty-one working days. Someone qualified reads your statements and writes it up.

A certified valuation from an accredited valuer runs $4,900 to $9,900 and takes
three to eight weeks. This is the one a court or the IRD will accept.

AccountIQ sits between the data report and the accounting firm. It reads your
actual statements, normalises the earnings, applies more than one method, and a
chartered accountant checks it before release. It comes back in three working
days.

**What $1,200 includes**

- Twelve to sixteen pages on your business
- Earnings normalised, with every adjustment listed
- More than one valuation method, and where they disagree
- The factors moving your number, named and explained
- Every assumption written down so it can be argued with
- William Cheong CA reading it before it reaches you
- A PDF you can hand to a buyer, a bank or a shareholder

**What it does not include**

- A certified or court-standard valuation
- Financial advice, or a recommendation about what to do
- An advisor sitting down and going through it with you
- Any independent verification of the figures you upload

**Who this is not for**

If you need a number for the Family Court, a formal dispute, an IRD position or
a relationship property settlement, you need a certified valuer, not this. [Name
who to ring.]

**How much is a business worth with $1 million in sales?**

Revenue on its own does not answer it. Two businesses turning over $1 million can
be worth very different amounts depending on what they earn after a market salary
for the owner, how much of the business walks out when the owner does, and
whether the revenue repeats.

**How many times earnings is a business worth?**

[Real range, with its source. Publish nothing here until the source sentence
exists.]

**Refunds**
[Read it. If you do not think it was worth the fee, reply to the email and I will
refund it. Needs Gate 5 and an implemented refund path before it can be said.]

## Sample report

**Heading**
A full valuation report, start to finish

**Opening**
This is a complete AccountIQ report for a made-up company, [Name], a [industry]
business turning over [amount]. Nothing is held back and there is no email form.
Read the whole thing and decide whether it is worth $1,200.

**Button:** Download the PDF

Then every page of the report, shown at a readable size, with a short note beside
each explaining what the section does and why it is there.

**At the end**
Your report will look like this one, with your numbers and your business.

**Button:** Get started

## About

**Heading**
Who is behind this

**William**

[Photograph]

[300 words from William. What he did before this, how long he has practised, what
he saw that made him build it. Written in his own voice, first person. This is
the part of the site that does the most work and it cannot be written for him.]

**Why the price is published**

Valuation fees are usually quoted after a phone call. That works for firms
selling advisory time, where the scope genuinely varies. AccountIQ is one report
with one scope, so there is nothing to quote. The number is on the site.

**What this is not**

An indicative valuation is a starting point for a decision, not a substitute for
advice, and it is not a certified valuation. It says so on the front page of the
report. If the number has to survive a court, a formal dispute or the IRD, you
need a registered valuer.

## Your data

**Heading**
Where your financial statements go

**Opening**
You are being asked to upload your annual accounts to a website. Here is exactly
what happens to them.

- **Stored:** [where, and in which country]
- **Opened by:** [who, and under what circumstances]
- **Processed by:** [which AI provider, and whether the data leaves New Zealand]
- **Kept for:** [how long, and how to have them deleted sooner]
- **Used for:** preparing your report and nothing else. Not for training, not
  shared, not sold.
- **Cover:** [professional indemnity position]

**Contact**
Ask anything about this at [contact address].

## How it works

**Heading**
How it works

1. **Upload your statements.** Your last two to three years of annual financial
   statements. PDF is fine.
2. **Answer questions about the business.** What you pay yourself, what happened
   once and will not happen again, who your biggest customers are, what happens
   if you take three months off. Roughly twenty minutes.
3. **See the fee and pay.** $1,200. The number does not change after you have
   uploaded.
4. **AccountIQ prepares the report,** and William reads it against your
   statements.
5. **Open the finished report** from your account, three working days later.

## For advisors

**Heading**
For accountants and business brokers

**Opening**
Your client asks what their business is worth. You either do it yourself, which
takes days you would rather bill elsewhere, or you send them to a valuation firm
that charges $2,250 and takes three weeks.

AccountIQ is a third option. An indicative report for $1,200 in three working
days, prepared from their statements and checked by a chartered accountant. It is
not a certified valuation and does not pretend to be, so it does not compete with
the work you would send to a registered valuer.

**What you get**
[Referral arrangement, white label option, what a firm earns. Needs deciding.]

**Contact**
[Contact address]
