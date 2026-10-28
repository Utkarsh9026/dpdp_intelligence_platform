"""Plain-language "how to fix" guidance per website checklist item (A1..K5).

Shown in the detailed website report. It is practical guidance, not legal advice: the rule engine
decides the status, this only says what a typical fix looks like. Keep entries short and actionable.
"""

FIX = {
    # A. Notice
    'A1': 'Put a short notice, or a clear link to the full privacy notice, directly beside every place you ask for data: sign-up, contact, demo, newsletter, checkout, careers and chat. It must be visible before the person submits.',
    'A2': 'List the categories of personal data you collect (for example name, email, phone, payment details, device identifiers, cookies). Replace vague lines such as "information you provide" with an itemised list.',
    'A3': 'For each purpose, say what you use the data for and which service or feature it enables. Avoid broad wording like "to improve our services". One line per purpose is enough.',
    'A4': 'Rewrite the notice in short, plain sentences with headings, and publish it as its own page rather than inside the terms and conditions. Aim for a reading level a general visitor can follow.',
    'A5': 'State how a person can withdraw consent (a link, an account setting or an email) and make it as easy as giving consent. Include the link to your website or app where the choice can be made.',
    'A6': 'Describe how to request access, correction, erasure and grievance redressal, and how to nominate another person. Give a form, email address or portal link, and say how quickly you respond.',
    'A7': 'Add a sentence explaining that a person can complain to the Data Protection Board of India if the grievance is not resolved, and how to do so. Keep it next to your own grievance route.',
    'A8': 'Offer the notice and consent request in English and in the other Eighth Schedule languages your visitors use. Add a visible language switcher and test that the translated notice loads.',
    'A9': 'For people who consented before the Act came into force, send a notice as soon as reasonably practicable (email, in-app message or banner). Keep a record that it was sent.',
    'A10': 'Add a "Last updated" date and a version number to the notice, and keep every earlier version in an archive so you can show what was in force on any date.',
    'A11': 'Link the privacy notice from the footer of every page and from each form or consent prompt. Check the link on mobile and inside checkout and login pages.',

    # B. Consent
    'B1': 'For each processing activity, record whether it rests on consent or on a legitimate use under section 7. Stop any activity that has neither, and do not use data for purposes the law forbids.',
    'B2': 'Remove pre-ticked boxes and wording such as "by continuing to browse you agree". Consent must come from a clear action, for example an unticked checkbox the person ticks or a button they press.',
    'B3': 'Ask for each purpose separately. Do not bundle marketing with sign-up or with accepting terms, and do not refuse the service because someone declines data that is not necessary for it.',
    'B4': 'Review every form field and remove the ones you do not need for the stated purpose. Mark genuinely optional fields as optional.',
    'B5': 'Write the consent request in plain language and include the contact details of your Data Protection Officer, or of another person who can answer questions about the data.',
    'B6': 'Remove any term that asks people to give up a legal right, such as the right to complain to the Board. Such a term is invalid, and keeping it creates risk.',
    'B7': 'Give a withdrawal route that takes the same number of clicks as giving consent: an unsubscribe link, an account setting and a footer link such as "Manage preferences". Give it equal prominence.',
    'B8': 'When consent is withdrawn, stop processing within a reasonable time, including at your Data Processors, and delete the data unless the law requires you to keep it. Document the steps and who does them.',
    'B9': 'Keep a consent log that records who consented, when, to which purposes, under which notice version and through which channel. You must be able to prove notice and consent if asked.',
    'B10': 'Optional for now. Plan to accept consent given through a registered Consent Manager once that framework is live, and let people use it instead of your own form.',
    'B11': 'Show a cookie banner with a Reject All button as prominent as Accept All, and separate switches for analytics, advertising and other categories. Load no non-essential trackers until the person agrees, and none after they reject.',
    'B12': 'Remove hidden decline options, pre-selected toggles and wording that pushes people to accept. Make the "no" choice as visible and as easy as the "yes" choice.',
    'B13': 'Pass the visitor\'s consent choice to your analytics and advertising tags (for example through a consent-mode setting in your tag manager) so that a change or withdrawal takes effect immediately.',

    # C. Legitimate uses
    'C1': 'Where people hand over data voluntarily, such as a contact form, use it only for that purpose and stop when they tell you to. Add the purpose to the form and delete the data when the request is closed.',
    'C2': 'Limit data from the careers page and employee portal to hiring, employment, protection against loss or liability, and benefits the employee asks for. Keep it out of marketing lists.',
    'C3': 'Keep a simple register of disclosures made because the law or a court required them: who asked, on what authority, what you shared and when.',

    # D. Children
    'D1': 'Decide whether children under 18 can use the site. If they can, add an age declaration or age gate, and record your assessment and its reasons.',
    'D2': 'Before processing a child\'s data, get verifiable consent from a parent or guardian, and check that the person is an identifiable adult. Use reliable details you already hold, or a verified token such as a digital locker.',
    'D3': 'For a person with a disability who has a lawful guardian, verify that the guardian was properly appointed by a court, designated authority or local level committee before accepting consent.',
    'D4': 'Switch off advertising pixels, behavioural tracking and targeted ads for users who may be children. Do not profile them for marketing.',
    'D5': 'Review features, content and data uses for anything likely to harm a child\'s well-being, such as exposure to harmful content or unsafe contact. Record the review and the changes you made.',
    'D6': 'If you rely on a Fourth Schedule exemption (for example a clinical establishment, school or email-only account), write down which exemption, why it applies, and the limits on what you do with the data.',

    # E. Rights and grievance
    'E1': 'Publish a prominent "Your privacy rights" page or footer link with a request form, email address or portal for access, correction, erasure and nomination requests.',
    'E2': 'Tell people what you need to identify them, for example their registered email or username, so they can make a request without guessing.',
    'E3': 'Publish the business contact details of your DPO, or of another person who can answer questions, on the notice and rights page. Repeat the same details in every reply to a rights request.',
    'E4': 'Set up a grievance process with a named contact, and publish the time you take to respond. The response time must not exceed 90 days; a shorter published target is better.',
    'E5': 'Prepare a way to give a person a summary of the data you hold, what you do with it, and which other Data Fiduciaries and Data Processors receive it. A template export is enough.',
    'E6': 'Create steps for correcting, completing, updating and erasing data on request, and for the cases where you must keep it. Assign an owner and a deadline.',
    'E7': 'Add a way for people to nominate someone to exercise their rights if they die or become unable to act, for example a form in the account area or a documented email route.',
    'E8': 'Run rights requests through a ticketing tool with identity verification, an owner and a deadline tracker, so none are missed and you can show your response times.',

    # F. Security
    'F1': 'Serve every page and form over HTTPS with a valid certificate, redirect HTTP to HTTPS, and fix mixed content by loading images, scripts and fonts over HTTPS too.',
    'F2': 'Encrypt personal data in transit and at rest, and mask or tokenise sensitive fields such as payment and ID numbers wherever the full value is not needed.',
    'F3': 'Restrict access to systems holding personal data: unique accounts, least privilege, multi-factor authentication for admins, and prompt removal of access when people leave.',
    'F4': 'Log access to personal data, review the logs regularly and set alerts for unusual activity, so you can detect and investigate unauthorised access.',
    'F5': 'Take regular encrypted backups, test restoring them, and write a continuity plan for when data or systems are lost or compromised.',
    'F6': 'Keep logs and the personal data needed to investigate incidents for at least one year, unless another law requires longer. Set the retention in your logging tools.',
    'F7': 'Put security obligations in every Data Processor contract: safeguards, breach reporting, sub-processor limits and return or deletion of data at the end.',
    'F8': 'Document the technical and organisational measures that make your safeguards work in practice: policies, training, reviews and testing, with an owner for each.',
    'F9': 'Set Secure and HttpOnly flags on cookies, add security headers (HSTS, Content-Security-Policy, X-Content-Type-Options, X-Frame-Options), remove exposed admin panels and backup files, and keep your CMS and plugins up to date.',
    'F10': 'Write a breach plan that tells each affected person, without delay, what happened, when, the likely consequences, what you are doing and the steps they can take. Name a contact and rehearse it.',
    'F11': 'Add to the breach plan a notice to the Data Protection Board without delay, then a detailed report within 72 hours (or longer if the Board allows in writing). Assign who files it.',

    # G. Retention
    'G1': 'Define how long you keep data for each purpose, and delete it when consent is withdrawn or the purpose ends unless the law requires retention. Make sure Data Processors delete it too.',
    'G2': 'If you are a large e-commerce, gaming or social media platform, erase data of inactive users after three years and warn them at least 48 hours before you do.',
    'G3': 'Keep personal data, traffic data and logs for at least one year for the purposes in the Seventh Schedule, then erase them unless another law needs longer. Reconcile this with your shorter purpose-based deadlines.',
    'G4': 'Add website data stores to the retention schedule: form submissions, the email inbox, CRM, analytics, chat transcripts and backups, each with a retention period and an owner.',

    # H. Processors and third parties
    'H1': 'List every third-party script, pixel, SDK, embed, font, CDN, tag manager, chat widget, payment and map or video service on the site, with its purpose and owner. Remove any you cannot justify.',
    'H2': 'Sign a written contract with each Data Processor that sets out what they may do with the data and the safeguards they must keep.',
    'H3': 'Remember you stay responsible for processing done on your behalf. Oversee your processors: review their security, ask for evidence and act on problems.',
    'H4': 'For ad networks and other third parties that use the data for their own purposes, either make sure they have their own lawful basis or get consent that covers the disclosure. Hold ad tags until consent is given.',
    'H5': 'Where you use data to make a decision about a person or pass it to another fiduciary, check it is complete, accurate and consistent first, and give people a way to correct it.',

    # I. Cross-border
    'I1': 'Identify where your servers and third-party endpoints are located and which are outside India. Record the country and the service in your data inventory.',
    'I2': 'Check that no transfer goes to a country the Central Government has restricted, and meet any conditions it sets by order. Review your transfer list whenever the notified list changes.',
    'I3': 'Mention in the privacy notice that data may be transferred outside India, and where possible name the countries or regions.',
    'I4': 'If a sector regulator such as the RBI sets stricter storage or transfer rules for you, follow them and record how you comply.',

    # J. Significant Data Fiduciary
    'J1': 'Check whether the Central Government has notified you as a Significant Data Fiduciary and record the answer. If you have not been notified, mark this section not applicable.',
    'J2': 'If notified, appoint a Data Protection Officer who is based in India, answers to the board, and is the point of contact for grievances. Publish their contact details.',
    'J3': 'If notified, appoint an independent data auditor to evaluate your compliance, and keep the appointment on record.',
    'J4': 'If notified, run a Data Protection Impact Assessment and an audit every 12 months, and send the Board a report of significant observations.',
    'J5': 'If notified, carry out due diligence that your algorithmic and other technical measures, such as scoring or profiling, do not put people\'s rights at risk.',
    'J6': 'If notified, keep the specified personal data and its traffic data within India, and document where it is stored.',

    # K. Governance
    'K1': 'Build a record of processing that maps each website data flow: what is collected, where it goes, who receives it and how long it is kept.',
    'K2': 'Name a person inside the company who owns privacy, and identify the DPO or contact person for questions and rights requests.',
    'K3': 'Train staff who handle personal data on the notice, consent, rights requests and breach reporting. Keep attendance records.',
    'K4': 'Prepare to respond to directions from the Board and to government requests for information: name who handles them and keep your records ready.',
    'K5': 'Read about the voluntary undertaking and mediation routes with the Board, and decide who in the company would use them if a problem arises.',
}
