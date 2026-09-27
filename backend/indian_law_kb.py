from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any

from .embeddings import embed_text, embed_texts
from . import db as _db


@dataclass
class LawSection:
    """Represents a section from Indian law statutes."""
    act_name: str
    act_short: str
    section_number: str
    section_title: str
    text: str
    old_act_name: str | None = None
    old_act_short: str | None = None
    old_section_number: str | None = None
    category: str | None = None
    punishment: str | None = None
    keywords: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


IPC_TO_BNS_MAP: dict[str, dict[str, Any]] = {
    "302": {
        "bns_section": "103",
        "title": "Murder",
        "description": "Whoever commits murder shall be punished with death, or imprisonment for life, and shall also be liable to fine.",
        "category": "offenses_against_body",
        "punishment": "Death or imprisonment for life, and fine",
        "keywords": ["murder", "killing", "homicide", "death"],
    },
    "304": {
        "bns_section": "105",
        "title": "Culpable Homicide not amounting to Murder",
        "description": "Whoever commits culpable homicide not amounting to murder shall be punished with imprisonment for life, or imprisonment up to 10 years, and fine.",
        "category": "offenses_against_body",
        "punishment": "Imprisonment for life or up to 10 years, and fine",
        "keywords": ["culpable homicide", "death", "killing"],
    },
    "306": {
        "bns_section": "108",
        "title": "Abetment of Suicide",
        "description": "If any person commits suicide, whoever abets the commission of such suicide, shall be punished with imprisonment up to 10 years, and fine.",
        "category": "offenses_against_body",
        "punishment": "Imprisonment up to 10 years, and fine",
        "keywords": ["suicide", "abetment", "instigation"],
    },
    "307": {
        "bns_section": "109",
        "title": "Attempt to Murder",
        "description": "Whoever does any act with such intention or knowledge, and under such circumstances that, if he by that act caused death, he would be guilty of murder, shall be punished.",
        "category": "offenses_against_body",
        "punishment": "Imprisonment up to 10 years, and fine; if hurt caused, imprisonment for life",
        "keywords": ["attempt", "murder", "intent to kill"],
    },
    "354": {
        "bns_section": "74",
        "title": "Assault or Criminal Force to Woman with Intent to Outrage her Modesty",
        "description": "Whoever assaults or uses criminal force to any woman, intending to outrage or knowing it to be likely that he will thereby outrage her modesty.",
        "category": "offenses_against_women",
        "punishment": "Imprisonment from 1 to 5 years, and fine",
        "keywords": ["assault", "woman", "modesty", "outrage", "molestation"],
    },
    "376": {
        "bns_section": "63",
        "title": "Rape",
        "description": "A man is said to commit rape if he has sexual intercourse with a woman under circumstances falling under any of the descriptions specified.",
        "category": "offenses_against_women",
        "punishment": "Rigorous imprisonment not less than 10 years, may extend to life, and fine",
        "keywords": ["rape", "sexual assault", "consent", "woman"],
    },
    "379": {
        "bns_section": "303",
        "title": "Theft",
        "description": "Whoever commits theft shall be punished with imprisonment up to 3 years, or with fine, or with both.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment up to 3 years, or fine, or both",
        "keywords": ["theft", "stealing", "dishonest", "movable property"],
    },
    "380": {
        "bns_section": "305",
        "title": "Theft in Dwelling House",
        "description": "Whoever commits theft in any building, tent or vessel used as a human dwelling, or for custody of property.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment up to 7 years, and fine",
        "keywords": ["theft", "house", "dwelling", "burglary"],
    },
    "384": {
        "bns_section": "308",
        "title": "Extortion",
        "description": "Whoever commits extortion shall be punished with imprisonment up to 3 years, or with fine, or with both.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment up to 3 years, or fine, or both",
        "keywords": ["extortion", "threat", "fear", "property"],
    },
    "392": {
        "bns_section": "309",
        "title": "Robbery",
        "description": "Whoever commits robbery shall be punished with rigorous imprisonment up to 10 years, and fine.",
        "category": "offenses_against_property",
        "punishment": "Rigorous imprisonment up to 10 years, and fine",
        "keywords": ["robbery", "theft", "force", "violence"],
    },
    "406": {
        "bns_section": "316",
        "title": "Criminal Breach of Trust",
        "description": "Whoever commits criminal breach of trust shall be punished with imprisonment up to 3 years, or with fine, or with both.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment up to 3 years, or fine, or both",
        "keywords": ["breach of trust", "misappropriation", "entrustment"],
    },
    "415": {
        "bns_section": "318",
        "title": "Cheating",
        "description": "Whoever, by deceiving any person, fraudulently or dishonestly induces the person so deceived to deliver any property.",
        "category": "offenses_against_property",
        "punishment": "Defined in subsequent sections",
        "keywords": ["cheating", "deception", "fraud", "dishonest"],
    },
    "420": {
        "bns_section": "318",
        "title": "Cheating and Dishonestly Inducing Delivery of Property",
        "description": "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property to any person, or to make, alter or destroy any valuable security.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment up to 7 years, and fine",
        "keywords": ["cheating", "fraud", "dishonest", "property", "inducement", "420"],
    },
    "498A": {
        "bns_section": "85",
        "title": "Cruelty by Husband or Relatives of Husband",
        "description": "Whoever, being the husband or the relative of the husband of a woman, subjects such woman to cruelty shall be punished.",
        "category": "offenses_against_women",
        "punishment": "Imprisonment up to 3 years, and fine",
        "keywords": ["cruelty", "husband", "dowry", "harassment", "matrimonial", "domestic violence"],
    },
    "499": {
        "bns_section": "356",
        "title": "Defamation",
        "description": "Whoever makes or publishes any imputation concerning any person intending to harm the reputation of such person.",
        "category": "defamation",
        "punishment": "Simple imprisonment up to 2 years, or fine, or both",
        "keywords": ["defamation", "reputation", "libel", "slander"],
    },
    "500": {
        "bns_section": "356",
        "title": "Punishment for Defamation",
        "description": "Whoever defames another shall be punished with simple imprisonment up to 2 years, or with fine, or with both.",
        "category": "defamation",
        "punishment": "Simple imprisonment up to 2 years, or fine, or both",
        "keywords": ["defamation", "punishment"],
    },
    "503": {
        "bns_section": "351",
        "title": "Criminal Intimidation",
        "description": "Whoever threatens another with any injury to his person, reputation or property, with intent to cause alarm.",
        "category": "criminal_intimidation",
        "punishment": "Imprisonment up to 2 years, or fine, or both",
        "keywords": ["threat", "intimidation", "alarm", "injury"],
    },
    "506": {
        "bns_section": "351",
        "title": "Punishment for Criminal Intimidation",
        "description": "Whoever commits the offence of criminal intimidation shall be punished with imprisonment up to 2 years, or with fine, or with both.",
        "category": "criminal_intimidation",
        "punishment": "Imprisonment up to 2 years, or fine, or both; if threat of death or grievous hurt, up to 7 years",
        "keywords": ["criminal intimidation", "threat", "punishment"],
    },
    "509": {
        "bns_section": "79",
        "title": "Word, Gesture or Act Intended to Insult the Modesty of a Woman",
        "description": "Whoever intending to insult the modesty of any woman, utters any word, makes any sound or gesture, or exhibits any object.",
        "category": "offenses_against_women",
        "punishment": "Simple imprisonment up to 3 years, and fine",
        "keywords": ["insult", "modesty", "woman", "gesture", "eve teasing"],
    },
    "34": {
        "bns_section": "3(5)",
        "title": "Acts Done by Several Persons in Furtherance of Common Intention",
        "description": "When a criminal act is done by several persons in furtherance of the common intention of all, each of such persons is liable for that act in the same manner as if it were done by him alone.",
        "category": "general_principles",
        "punishment": "Varies based on the act committed",
        "keywords": ["common intention", "joint liability", "several persons", "shared intention"],
    },
    "107": {
        "bns_section": "45",
        "title": "Abetment of a Thing",
        "description": "A person abets the doing of a thing who instigates any person to do that thing; or engages with one or more other persons in any conspiracy; or intentionally aids the commission of an act.",
        "category": "abetment",
        "punishment": "Same as the principal offence abetted",
        "keywords": ["abetment", "instigation", "conspiracy", "aid", "facilitation"],
    },
    "120B": {
        "bns_section": "61",
        "title": "Punishment for Criminal Conspiracy",
        "description": "Whoever is a party to a criminal conspiracy to commit an offence punishable with death or imprisonment for life shall be punished in the same manner as if he had abetted such offence.",
        "category": "conspiracy",
        "punishment": "Same as abetting the offence conspired; or imprisonment up to 6 months if minor offence",
        "keywords": ["criminal conspiracy", "conspiracy", "120B", "joint plan"],
    },
    "323": {
        "bns_section": "115",
        "title": "Voluntarily Causing Hurt",
        "description": "Whoever voluntarily causes hurt shall be punished with imprisonment of either description up to 1 year, or with fine up to 1000 rupees, or with both.",
        "category": "offenses_against_body",
        "punishment": "Imprisonment up to 1 year, or fine up to Rs. 1000, or both",
        "keywords": ["hurt", "assault", "bodily harm", "injury", "beat"],
    },
    "325": {
        "bns_section": "116",
        "title": "Voluntarily Causing Grievous Hurt",
        "description": "Whoever voluntarily causes grievous hurt shall be punished with imprisonment up to 7 years, and fine.",
        "category": "offenses_against_body",
        "punishment": "Imprisonment up to 7 years, and fine",
        "keywords": ["grievous hurt", "serious injury", "broken bone", "permanent disability"],
    },
    "326": {
        "bns_section": "117",
        "title": "Voluntarily Causing Grievous Hurt by Dangerous Weapons or Means",
        "description": "Whoever causes grievous hurt by means of any instrument for shooting, stabbing or cutting, or any instrument which is likely to cause death, or by fire, heated substance, poison, explosive, or acid.",
        "category": "offenses_against_body",
        "punishment": "Imprisonment for life, or imprisonment up to 10 years, and fine",
        "keywords": ["grievous hurt", "weapon", "acid attack", "knife", "gun", "dangerous weapon"],
    },
    "354A": {
        "bns_section": "75",
        "title": "Sexual Harassment",
        "description": "A man committing physical contact and advances involving unwelcome and explicit sexual overtures; demanding or requesting for sexual favours; showing pornography against the will of a woman; making sexually coloured remarks.",
        "category": "offenses_against_women",
        "punishment": "Imprisonment up to 3 years, or fine, or both; up to 1 year for verbal remarks",
        "keywords": ["sexual harassment", "workplace harassment", "unwelcome advances", "POSH", "woman"],
    },
    "354C": {
        "bns_section": "77",
        "title": "Voyeurism",
        "description": "Any man who watches or captures the image of a woman engaging in a private act in circumstances where she would usually have the expectation of not being observed.",
        "category": "offenses_against_women",
        "punishment": "First conviction: 1 to 3 years and fine; subsequent: 3 to 7 years and fine",
        "keywords": ["voyeurism", "privacy", "spying", "hidden camera", "woman"],
    },
    "354D": {
        "bns_section": "78",
        "title": "Stalking",
        "description": "Any man who follows a woman and contacts or attempts to contact such woman to foster personal interaction repeatedly despite a clear indication of disinterest by the woman.",
        "category": "offenses_against_women",
        "punishment": "First conviction: up to 3 years and fine; subsequent: up to 5 years and fine",
        "keywords": ["stalking", "following", "harassment", "cyberstalking", "repeated contact"],
    },
    "375": {
        "bns_section": "63",
        "title": "Rape (Definition)",
        "description": "A man is said to commit rape if he penetrates or manipulates any part of a woman's body without her consent or against her will, or when consent is obtained by force, threat, fraud, intoxication, or misconception.",
        "category": "offenses_against_women",
        "punishment": "As per Section 376 — rigorous imprisonment not less than 10 years",
        "keywords": ["rape", "sexual assault", "consent", "definition", "sexual violence"],
    },
    "376D": {
        "bns_section": "70",
        "title": "Gang Rape",
        "description": "Where a woman is raped by one or more persons constituting a group or acting in furtherance of a common intention, each person shall be deemed to have committed the offence of rape.",
        "category": "offenses_against_women",
        "punishment": "Rigorous imprisonment not less than 20 years, may extend to life, and fine",
        "keywords": ["gang rape", "group", "common intention", "multiple perpetrators"],
    },
    "395": {
        "bns_section": "310",
        "title": "Dacoity",
        "description": "When five or more persons conjointly commit or attempt to commit a robbery, or where the whole number of persons conjointly committing or attempting to commit a robbery and aiding such commission is five or more.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment for life, or rigorous imprisonment up to 10 years, and fine",
        "keywords": ["dacoity", "robbery", "five persons", "gang robbery", "armed robbery"],
    },
    "409": {
        "bns_section": "316",
        "title": "Criminal Breach of Trust by Public Servant or Banker",
        "description": "Whoever, being in any manner entrusted with property in his capacity as a public servant, banker, merchant, broker, attorney or agent, commits criminal breach of trust in respect of that property.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment for life, or imprisonment up to 10 years, and fine",
        "keywords": ["criminal breach of trust", "public servant", "banker", "misappropriation", "embezzlement"],
    },
    "411": {
        "bns_section": "317",
        "title": "Dishonestly Receiving Stolen Property",
        "description": "Whoever dishonestly receives or retains any stolen property, knowing or having reason to believe the same to be stolen property, shall be punished.",
        "category": "offenses_against_property",
        "punishment": "Imprisonment up to 3 years, or fine, or both",
        "keywords": ["stolen property", "receiving stolen", "dishonestly", "handler"],
    },
    "463": {
        "bns_section": "334",
        "title": "Forgery",
        "description": "Whoever makes any false document or false electronic record or part of a document with intent to cause damage or injury to the public or to any person, or to support any claim or title, or to cause any person to part with property.",
        "category": "forgery",
        "punishment": "As per specific forgery sections",
        "keywords": ["forgery", "false document", "fake", "fraud", "fabrication"],
    },
    "467": {
        "bns_section": "338",
        "title": "Forgery of Valuable Security or Will",
        "description": "Whoever forges a document which purports to be a valuable security, or a will, or an authority to adopt a son, or which purports to give authority to any person to make or transfer any valuable security.",
        "category": "forgery",
        "punishment": "Imprisonment for life, or imprisonment up to 10 years, and fine",
        "keywords": ["forgery", "valuable security", "will", "bond", "fake will"],
    },
    "468": {
        "bns_section": "339",
        "title": "Forgery for Purpose of Cheating",
        "description": "Whoever commits forgery, intending that the document or electronic record forged shall be used for the purpose of cheating, shall be punished.",
        "category": "forgery",
        "punishment": "Imprisonment up to 7 years, and fine",
        "keywords": ["forgery", "cheating", "fraud", "fake document for cheating"],
    },
    "471": {
        "bns_section": "341",
        "title": "Using as Genuine a Forged Document",
        "description": "Whoever fraudulently or dishonestly uses as genuine, any document or electronic record which he knows or has reason to believe to be a forged document or electronic record.",
        "category": "forgery",
        "punishment": "Same as for forgery of that document",
        "keywords": ["forged document", "using fake document", "fraudulent use", "counterfeit"],
    },
}

CRPC_TO_BNSS_MAP: dict[str, dict[str, Any]] = {
    "41": {
        "bnss_section": "35",
        "title": "When Police May Arrest Without Warrant",
        "description": "Any police officer may without an order from a Magistrate and without a warrant, arrest any person in specified circumstances.",
        "category": "arrest",
        "keywords": ["arrest", "warrant", "police", "cognizable"],
    },
    "154": {
        "bnss_section": "173",
        "title": "First Information Report (FIR)",
        "description": "Every information relating to the commission of a cognizable offence shall be reduced to writing by the officer in charge of a police station.",
        "category": "investigation",
        "keywords": ["fir", "first information report", "complaint", "cognizable", "police station"],
    },
    "156": {
        "bnss_section": "175",
        "title": "Police Officer's Power to Investigate Cognizable Case",
        "description": "Any officer in charge of a police station may investigate any cognizable case without the order of a Magistrate.",
        "category": "investigation",
        "keywords": ["investigation", "cognizable", "police"],
    },
    "161": {
        "bnss_section": "180",
        "title": "Examination of Witnesses by Police",
        "description": "Any police officer making an investigation may examine orally any person supposed to be acquainted with the facts and circumstances of the case.",
        "category": "investigation",
        "keywords": ["witness", "examination", "statement", "police"],
    },
    "164": {
        "bnss_section": "183",
        "title": "Recording of Confessions and Statements",
        "description": "Any Metropolitan Magistrate or Judicial Magistrate may record any confession or statement made to him in the course of an investigation.",
        "category": "investigation",
        "keywords": ["confession", "statement", "magistrate", "recording"],
    },
    "167": {
        "bnss_section": "187",
        "title": "Procedure When Investigation Cannot be Completed in 24 Hours",
        "description": "Whenever any person is arrested and detained in custody, and it appears that the investigation cannot be completed within 24 hours.",
        "category": "remand",
        "keywords": ["remand", "custody", "detention", "24 hours", "magistrate"],
    },
    "173": {
        "bnss_section": "193",
        "title": "Report of Police Officer on Completion of Investigation (Chargesheet)",
        "description": "Every investigation shall be completed without unnecessary delay and the officer shall forward a report to the Magistrate.",
        "category": "investigation",
        "keywords": ["chargesheet", "final report", "investigation", "completion"],
    },
    "190": {
        "bnss_section": "210",
        "title": "Cognizance of Offences by Magistrates",
        "description": "Any Magistrate of the first class may take cognizance of any offence upon receiving a complaint, police report, or information.",
        "category": "cognizance",
        "keywords": ["cognizance", "magistrate", "complaint", "offence"],
    },
    "200": {
        "bnss_section": "223",
        "title": "Examination of Complainant",
        "description": "A Magistrate taking cognizance of an offence on complaint shall examine upon oath the complainant and the witnesses present.",
        "category": "complaint",
        "keywords": ["complainant", "examination", "oath", "magistrate"],
    },
    "227": {
        "bnss_section": "250",
        "title": "Discharge",
        "description": "If upon consideration of the record and documents, the Judge considers that there is not sufficient ground for proceeding against the accused, he shall discharge the accused.",
        "category": "trial",
        "keywords": ["discharge", "accused", "insufficient ground"],
    },
    "228": {
        "bnss_section": "251",
        "title": "Framing of Charge",
        "description": "If the Judge is of opinion that there is ground for presuming that the accused has committed an offence, he shall frame a charge.",
        "category": "trial",
        "keywords": ["charge", "framing", "accused", "trial"],
    },
    "313": {
        "bnss_section": "351",
        "title": "Power to Examine the Accused",
        "description": "The Court may at any stage examine the accused for the purpose of enabling him to explain any circumstances appearing in the evidence against him.",
        "category": "trial",
        "keywords": ["accused", "examination", "statement", "313"],
    },
    "436": {
        "bnss_section": "480",
        "title": "Bail in Bailable Offences",
        "description": "When any person accused of a bailable offence is arrested or detained, he shall be released on bail.",
        "category": "bail",
        "keywords": ["bail", "bailable", "release", "bond"],
    },
    "437": {
        "bnss_section": "480",
        "title": "Bail in Non-Bailable Offences",
        "description": "When any person accused of a non-bailable offence is arrested or detained, he may be released on bail at the discretion of the Court.",
        "category": "bail",
        "keywords": ["bail", "non-bailable", "discretion", "court"],
    },
    "438": {
        "bnss_section": "482",
        "title": "Anticipatory Bail",
        "description": "Where any person has reason to believe that he may be arrested on accusation of having committed a non-bailable offence, he may apply for anticipatory bail.",
        "category": "bail",
        "keywords": ["anticipatory bail", "pre-arrest", "apprehension"],
    },
    "439": {
        "bnss_section": "483",
        "title": "Special Powers of High Court or Court of Session Regarding Bail",
        "description": "A High Court or Court of Session may direct that any person accused of an offence and in custody be released on bail.",
        "category": "bail",
        "keywords": ["bail", "high court", "sessions court", "special powers"],
    },
    "482": {
        "bnss_section": "528",
        "title": "Inherent Powers of High Court",
        "description": "Nothing in this Code shall be deemed to limit or affect the inherent powers of the High Court to make such orders as may be necessary.",
        "category": "high_court",
        "keywords": ["inherent powers", "high court", "quashing", "482"],
    },
    "125": {
        "bnss_section": "144",
        "title": "Order for Maintenance of Wives, Children and Parents",
        "description": "If any person having sufficient means neglects or refuses to maintain his wife, his legitimate or illegitimate minor child, or his father or mother unable to maintain themselves, a Magistrate may order monthly maintenance.",
        "category": "maintenance",
        "keywords": ["maintenance", "wife", "children", "parents", "alimony", "monthly allowance", "neglect"],
    },
    "144": {
        "bnss_section": "163",
        "title": "Power to Issue Orders in Urgent Cases of Nuisance or Apprehended Danger",
        "description": "A District Magistrate or Sub-divisional Magistrate may by a written order direct any person to abstain from a certain act or to take certain order, in urgent cases of nuisance or apprehended danger to public peace.",
        "category": "public_order",
        "keywords": ["section 144", "prohibitory order", "unlawful assembly", "curfew", "public peace", "nuisance"],
    },
    "145": {
        "bnss_section": "164",
        "title": "Procedure Where Dispute Concerning Land is Likely to Cause Breach of Peace",
        "description": "Whenever a Magistrate is satisfied that a dispute likely to cause a breach of the peace exists concerning any land or water or the boundaries thereof, he shall make an order requiring the parties to attend.",
        "category": "civil_dispute",
        "keywords": ["land dispute", "possession", "breach of peace", "property dispute", "boundary"],
    },
}

OTHER_IMPORTANT_LAWS: list[dict[str, Any]] = [
    {
        "act_name": "Indian Contract Act, 1872",
        "act_short": "ICA",
        "sections": {
            "2": {"title": "Interpretation Clause", "description": "Definitions of proposal, promise, agreement, contract, void agreement, etc.", "keywords": ["definition", "contract", "agreement", "promise"]},
            "10": {"title": "What Agreements are Contracts", "description": "All agreements are contracts if made by free consent of parties competent to contract, for lawful consideration and lawful object.", "keywords": ["valid contract", "free consent", "competent", "lawful"]},
            "14": {"title": "Free Consent", "description": "Consent is said to be free when it is not caused by coercion, undue influence, fraud, misrepresentation, or mistake.", "keywords": ["consent", "coercion", "fraud", "misrepresentation"]},
            "23": {"title": "Unlawful Consideration and Object", "description": "The consideration or object of an agreement is unlawful if it is forbidden by law, defeats provisions of law, is fraudulent, involves injury, or is immoral.", "keywords": ["unlawful", "illegal", "void", "consideration"]},
            "73": {"title": "Compensation for Breach", "description": "When a contract has been broken, the party who suffers is entitled to receive compensation for any loss or damage caused.", "keywords": ["breach", "compensation", "damages", "loss"]},
            "74": {"title": "Liquidated Damages", "description": "When a contract has been broken, if a sum is named in the contract as the amount to be paid in case of breach, the party complaining may receive reasonable compensation not exceeding the amount so named.", "keywords": ["liquidated damages", "penalty", "breach", "compensation"]},
        },
    },
    {
        "act_name": "Consumer Protection Act, 2019",
        "act_short": "CPA",
        "sections": {
            "2(7)": {"title": "Definition of Consumer", "description": "Consumer means any person who buys goods or hires services for consideration.", "keywords": ["consumer", "buyer", "goods", "services"]},
            "2(9)": {"title": "Definition of Defect", "description": "Defect means any fault, imperfection or shortcoming in the quality, quantity, potency, purity or standard.", "keywords": ["defect", "fault", "quality", "standard"]},
            "2(11)": {"title": "Definition of Deficiency", "description": "Deficiency means any fault, imperfection, shortcoming or inadequacy in the quality, nature and manner of performance of service.", "keywords": ["deficiency", "service", "inadequacy", "performance"]},
            "34": {"title": "Jurisdiction of District Commission", "description": "District Commission shall have jurisdiction to entertain complaints where value of goods or services does not exceed one crore rupees.", "keywords": ["district commission", "jurisdiction", "complaint", "one crore"]},
            "35": {"title": "Jurisdiction of State Commission", "description": "State Commission shall have jurisdiction where value exceeds one crore but does not exceed ten crore rupees.", "keywords": ["state commission", "jurisdiction", "ten crore"]},
            "47": {"title": "Penalties", "description": "Where a trader or person fails to comply with any order, he shall be punishable with imprisonment or fine or both.", "keywords": ["penalty", "non-compliance", "punishment"]},
        },
    },
    {
        "act_name": "Negotiable Instruments Act, 1881",
        "act_short": "NI Act",
        "sections": {
            "138": {"title": "Dishonour of Cheque for Insufficiency of Funds", "description": "Where any cheque is returned unpaid due to insufficient funds, the drawer shall be deemed to have committed an offence.", "keywords": ["cheque bounce", "dishonour", "insufficient funds", "138"]},
            "139": {"title": "Presumption in Favour of Holder", "description": "It shall be presumed that the holder of a cheque received the cheque for discharge of any debt or liability.", "keywords": ["presumption", "holder", "debt", "liability"]},
            "141": {"title": "Offences by Companies", "description": "If the person committing an offence under section 138 is a company, every person who was in charge of the company shall be deemed guilty.", "keywords": ["company", "director", "liability", "138"]},
            "142": {"title": "Cognizance of Offences", "description": "No court shall take cognizance of any offence punishable under section 138 except upon a complaint in writing made by the payee.", "keywords": ["cognizance", "complaint", "payee", "138"]},
            "143": {"title": "Power of Court to Try Cases Summarily", "description": "Notwithstanding anything contained in the Code, all offences under this Chapter shall be tried by a Judicial Magistrate of the first class or by a Metropolitan Magistrate.", "keywords": ["summary trial", "magistrate", "138"],},
        },
    },
    {
        "act_name": "Information Technology Act, 2000",
        "act_short": "IT Act",
        "sections": {
            "43": {"title": "Penalty for Damage to Computer System", "description": "If any person without permission accesses or downloads data from a computer, he shall be liable to pay damages.", "keywords": ["hacking", "unauthorized access", "computer", "damage"]},
            "66": {"title": "Computer Related Offences", "description": "If any person dishonestly or fraudulently does any act referred to in section 43, he shall be punishable with imprisonment up to 3 years or fine up to 5 lakh rupees.", "keywords": ["hacking", "fraud", "computer crime", "cyber"]},
            "66A": {"title": "Sending Offensive Messages (Struck Down)", "description": "This section was struck down by the Supreme Court in Shreya Singhal case as unconstitutional.", "keywords": ["offensive message", "struck down", "unconstitutional"]},
            "66C": {"title": "Identity Theft", "description": "Whoever fraudulently or dishonestly makes use of the electronic signature, password or any other unique identification feature of any other person.", "keywords": ["identity theft", "password", "fraud", "impersonation"]},
            "66D": {"title": "Cheating by Personation using Computer Resource", "description": "Whoever by means of any communication device or computer resource cheats by personation.", "keywords": ["cheating", "personation", "online fraud", "impersonation"]},
            "67": {"title": "Publishing Obscene Material", "description": "Whoever publishes or transmits or causes to be published in electronic form any material which is obscene.", "keywords": ["obscene", "pornography", "electronic", "publish"]},
            "72": {"title": "Breach of Confidentiality and Privacy", "description": "Any person who has secured access to any electronic record, book, register, correspondence, information, document or other material, and discloses it without consent.", "keywords": ["privacy", "confidentiality", "disclosure", "breach"]},
        },
    },
    {
        "act_name": "Constitution of India",
        "act_short": "COI",
        "sections": {
            "14": {"title": "Equality Before Law", "description": "The State shall not deny to any person equality before the law or the equal protection of the laws within the territory of India.", "keywords": ["equality", "law", "discrimination", "fundamental right"]},
            "15": {"title": "Prohibition of Discrimination", "description": "The State shall not discriminate against any citizen on grounds only of religion, race, caste, sex, place of birth or any of them.", "keywords": ["discrimination", "religion", "caste", "sex", "fundamental right"]},
            "19": {"title": "Protection of Certain Rights", "description": "All citizens shall have the right to freedom of speech and expression, to assemble peaceably, to form associations, to move freely, to reside and settle, and to practice any profession.", "keywords": ["freedom", "speech", "expression", "assembly", "movement"]},
            "20": {"title": "Protection in Respect of Conviction for Offences", "description": "No person shall be convicted of any offence except for violation of a law in force at the time of the commission of the act charged as an offence.", "keywords": ["double jeopardy", "self-incrimination", "retrospective law", "conviction"]},
            "21": {"title": "Protection of Life and Personal Liberty", "description": "No person shall be deprived of his life or personal liberty except according to procedure established by law.", "keywords": ["life", "liberty", "due process", "fundamental right", "article 21"]},
            "21A": {"title": "Right to Education", "description": "The State shall provide free and compulsory education to all children of the age of 6 to 14 years in such manner as the State may determine.", "keywords": ["right to education", "children", "free education", "RTE"]},
            "22": {"title": "Protection Against Arrest and Detention", "description": "No person who is arrested shall be detained in custody without being informed of the grounds for such arrest. Every person detained has the right to consult and be defended by a legal practitioner.", "keywords": ["arrest", "detention", "grounds", "legal aid", "lawyer"]},
            "32": {"title": "Remedies for Enforcement of Fundamental Rights", "description": "The right to move the Supreme Court for enforcement of fundamental rights is guaranteed. The Supreme Court shall have power to issue writs including habeas corpus, mandamus, prohibition, quo warranto and certiorari.", "keywords": ["supreme court", "writ", "fundamental rights", "enforcement", "habeas corpus"]},
            "39A": {"title": "Equal Justice and Free Legal Aid", "description": "The State shall secure that the operation of the legal system promotes justice on a basis of equal opportunity, and shall provide free legal aid, by suitable legislation or schemes, to ensure that opportunities for securing justice are not denied to any citizen.", "keywords": ["free legal aid", "equal justice", "legal help", "poor"]},
            "226": {"title": "Power of High Courts to Issue Writs", "description": "Every High Court shall have power to issue writs for enforcement of fundamental rights and for any other purpose.", "keywords": ["high court", "writ", "habeas corpus", "mandamus", "certiorari"]},
        },
    },
    {
        "act_name": "Bharatiya Sakshya Adhiniyam, 2023",
        "act_short": "BSA",
        "sections": {
            "2(1)(f)": {"title": "Evidence Defined", "description": "Evidence means and includes all statements which the Court permits or requires to be made before it by witnesses, and all documents including electronic or digital records produced for the inspection of the Court.", "keywords": ["evidence", "definition", "witness", "document", "electronic record"]},
            "16": {"title": "Admission", "description": "An admission is a statement, oral or documentary or contained in electronic form, which suggests any inference as to any fact in issue or relevant fact.", "keywords": ["admission", "confession", "statement", "acknowledgment"]},
            "22": {"title": "Confession Caused by Inducement, Threat or Promise", "description": "A confession made by an accused person is irrelevant in a criminal proceeding if the making of the confession appears to have been caused by any inducement, threat or promise.", "keywords": ["confession", "inducement", "threat", "promise", "involuntary"]},
            "23": {"title": "Confession to Police Officer", "description": "No confession made to a police officer shall be proved as against a person accused of any offence.", "keywords": ["confession", "police officer", "inadmissible", "custodial confession"]},
            "57": {"title": "Admissibility of Electronic Records", "description": "Any information contained in an electronic record which is printed on paper, stored, recorded or copied in optical or magnetic media produced by a computer shall be deemed to be a document and admissible if conditions are fulfilled.", "keywords": ["electronic evidence", "digital evidence", "cyber evidence", "admissibility", "65B"]},
            "116": {"title": "Burden of Proof", "description": "Whoever desires any Court to give judgment as to any legal right or liability dependent on the existence of facts which he asserts, must prove that those facts exist.", "keywords": ["burden of proof", "onus", "prove", "prosecution", "accusation"]},
            "118": {"title": "Presumption of Innocence", "description": "The burden of proving the guilt of the accused lies on the prosecution. Every person is presumed innocent unless proven guilty beyond reasonable doubt.", "keywords": ["presumption of innocence", "reasonable doubt", "burden on prosecution", "innocent"]},
        },
    },
    {
        "act_name": "Transfer of Property Act, 1882",
        "act_short": "TPA",
        "sections": {
            "5": {"title": "Transfer of Property Defined", "description": "In the following sections 'transfer of property' means an act by which a living person conveys property, in present or in future, to one or more other living persons, or to himself, or to himself and one or more other living persons.", "keywords": ["transfer", "property", "conveyance", "living person"]},
            "54": {"title": "Sale Defined", "description": "Sale is a transfer of ownership in exchange for a price paid or promised or part-paid and part-promised. Sale deed must be registered for immovable property above Rs. 100.", "keywords": ["sale", "property sale", "sale deed", "ownership", "purchase"]},
            "58": {"title": "Mortgage Defined", "description": "A mortgage is the transfer of an interest in specific immovable property for the purpose of securing the payment of money advanced or to be advanced by way of loan.", "keywords": ["mortgage", "home loan", "property loan", "security", "bank loan"]},
            "105": {"title": "Lease Defined", "description": "A lease of immovable property is a transfer of a right to enjoy such property, made for a certain time, express or implied, or in perpetuity, in consideration of a price paid or promised.", "keywords": ["lease", "rent", "tenancy", "landlord", "tenant", "rental agreement"]},
            "108": {"title": "Rights and Liabilities of Lessor and Lessee", "description": "The lessor is bound to disclose material defects. The lessee must pay rent, maintain property, and not use it for purposes other than intended.", "keywords": ["landlord rights", "tenant rights", "lessor", "lessee", "duties"]},
            "122": {"title": "Gift Defined", "description": "Gift is the transfer of certain existing movable or immovable property made voluntarily and without consideration, by one person, called the donor, to another, called the donee.", "keywords": ["gift", "donation", "gifted property", "will", "donor", "donee"]},
        },
    },
    {
        "act_name": "Protection of Children from Sexual Offences Act, 2012",
        "act_short": "POCSO",
        "sections": {
            "3": {"title": "Penetrative Sexual Assault", "description": "A person is said to commit 'penetrative sexual assault' if he penetrates his penis or any object or any part of the body into the vagina, mouth, urethra or anus of a child.", "keywords": ["POCSO", "child abuse", "penetrative assault", "sexual offence child"]},
            "7": {"title": "Sexual Assault", "description": "Whoever, with sexual intent touches the vagina, penis, anus or breast of the child or makes the child touch the vagina, penis, anus or breast of such person or any other person.", "keywords": ["POCSO", "child sexual assault", "touching", "molestation child"]},
            "11": {"title": "Sexual Harassment of a Child", "description": "A person is said to commit sexual harassment upon a child when such person makes a child exhibit his body or any part of his body so as it is seen by such person or any other person.", "keywords": ["POCSO", "child harassment", "sexual harassment minor", "exhibitionism"]},
            "19": {"title": "Reporting of Offences", "description": "Any person, who has apprehension that an offence under this Act is likely to be committed or has knowledge that such an offence has been committed, shall provide such information to the Special Juvenile Police Unit.", "keywords": ["POCSO", "reporting obligation", "mandatory reporting", "child protection"]},
            "28": {"title": "Special Court", "description": "The State Government shall designate one or more courts as a Special Court to try offences under this Act for each district.", "keywords": ["POCSO", "special court", "child court", "fast track"]},
        },
    },
    {
        "act_name": "Protection of Women from Domestic Violence Act, 2005",
        "act_short": "PWDVA",
        "sections": {
            "3": {"title": "Definition of Domestic Violence", "description": "Any act, omission or commission or conduct of the respondent that harms or injures or endangers the health, safety, life, limb or well-being of the aggrieved person including physical, sexual, verbal, emotional and economic abuse.", "keywords": ["domestic violence", "definition", "physical abuse", "emotional abuse", "economic abuse"]},
            "12": {"title": "Application to Magistrate", "description": "An aggrieved person or a Protection Officer or any other person on behalf of the aggrieved person may present an application to the Magistrate seeking relief under the Act.", "keywords": ["domestic violence", "application", "magistrate", "complaint", "protection order"]},
            "17": {"title": "Right to Reside in Shared Household", "description": "Notwithstanding anything contained in any other law, every woman in a domestic relationship shall have the right to reside in the shared household.", "keywords": ["shared household", "right to reside", "matrimonial home", "wife", "domestic violence"]},
            "18": {"title": "Protection Orders", "description": "The Magistrate may pass a protection order in favour of the aggrieved person and prohibit the respondent from committing any act of domestic violence, entering the workplace or school, communicating with the aggrieved person.", "keywords": ["protection order", "restraining order", "domestic violence", "court order"]},
            "20": {"title": "Monetary Reliefs", "description": "The Magistrate may direct the respondent to pay monetary relief to meet the expenses incurred and losses suffered by the aggrieved person and any child as a result of the domestic violence.", "keywords": ["monetary relief", "compensation", "domestic violence", "financial support", "maintenance"]},
        },
    },
    {
        "act_name": "Right to Information Act, 2005",
        "act_short": "RTI",
        "sections": {
            "3": {"title": "Right to Information", "description": "Subject to the provisions of this Act, all citizens shall have the right to information.", "keywords": ["RTI", "right to information", "citizen", "government information"]},
            "4": {"title": "Obligations of Public Authorities", "description": "Every public authority shall maintain all its records duly catalogued and indexed, and publish all relevant facts while formulating important policies or announcing decisions.", "keywords": ["RTI", "public authority", "transparency", "proactive disclosure"]},
            "7": {"title": "Disposal of Request", "description": "The Central Public Information Officer shall dispose of every request within 30 days of its receipt. Where the request pertains to the life or liberty of a person, it shall be disposed of within 48 hours.", "keywords": ["RTI", "30 days", "48 hours", "response time", "public information officer"]},
            "8": {"title": "Exemption from Disclosure of Information", "description": "There shall be no obligation to give any citizen information that would prejudicially affect the sovereignty and integrity of India, security of the State, strategic interests, or which has been expressly forbidden by courts.", "keywords": ["RTI", "exemption", "national security", "disclosure exempt", "privacy"]},
            "19": {"title": "Appeal", "description": "Any person who does not receive a decision within 30 days or is aggrieved by a decision may prefer an appeal to the officer designated by the public authority.", "keywords": ["RTI", "appeal", "first appeal", "second appeal", "information commission"]},
        },
    },
    {
        "act_name": "Industrial Disputes Act, 1947",
        "act_short": "IDA",
        "sections": {
            "2(s)": {"title": "Workman Defined", "description": "Workman means any person including an apprentice employed in any industry to do any manual, unskilled, skilled, technical, operational, clerical or supervisory work for hire or reward.", "keywords": ["workman", "employee", "industrial dispute", "worker", "labour"]},
            "25F": {"title": "Conditions Precedent to Retrenchment", "description": "No workman who has been in continuous service for not less than one year under an employer shall be retrenched by that employer until the workman has been given one month's notice or wages in lieu of notice.", "keywords": ["retrenchment", "layoff", "termination", "one month notice", "compensation"]},
            "25G": {"title": "Procedure for Retrenchment", "description": "The employer shall ordinarily retrench the workman who was the last person to be employed in that category. This is the 'last come first go' principle.", "keywords": ["retrenchment", "last come first go", "LIFO", "layoff procedure"]},
            "33": {"title": "Conditions of Service During Pendency of Proceedings", "description": "During the pendency of any conciliation proceeding, no employer shall alter the conditions of service of any workman or discharge or punish such workman.", "keywords": ["protected workman", "conditions of service", "during proceedings", "employer restrictions"]},
            "10": {"title": "Reference of Disputes to Boards, Courts or Tribunals", "description": "Where the appropriate Government is of opinion that any industrial dispute exists or is apprehended, it may refer the dispute to conciliation, Labour Court, Industrial Tribunal, or National Tribunal.", "keywords": ["industrial dispute", "reference", "tribunal", "labour court", "conciliation"]},
        },
    },
]


def normalize_section_number(section: str) -> str:
    """Normalize section number for matching."""
    section = section.strip().upper()
    section = re.sub(r"^(SECTION|SEC\.?|S\.?)\s*", "", section, flags=re.IGNORECASE)
    section = re.sub(r"\s+", "", section)
    return section


def lookup_ipc_section(section: str) -> dict[str, Any] | None:
    """Look up an IPC section and return its details with BNS mapping."""
    normalized = normalize_section_number(section)
    
    if normalized in IPC_TO_BNS_MAP:
        data = IPC_TO_BNS_MAP[normalized]
        return {
            "found": True,
            "act": "Indian Penal Code, 1860",
            "act_short": "IPC",
            "section": normalized,
            "title": data["title"],
            "description": data["description"],
            "category": data["category"],
            "punishment": data.get("punishment"),
            "keywords": data.get("keywords", []),
            "new_law": {
                "act": "Bharatiya Nyaya Sanhita, 2023",
                "act_short": "BNS",
                "section": data["bns_section"],
            },
        }
    return None


def lookup_bns_section(section: str) -> dict[str, Any] | None:
    """Look up a BNS section and return its details with IPC mapping."""
    normalized = normalize_section_number(section)
    
    for ipc_section, data in IPC_TO_BNS_MAP.items():
        if data["bns_section"] == normalized:
            return {
                "found": True,
                "act": "Bharatiya Nyaya Sanhita, 2023",
                "act_short": "BNS",
                "section": normalized,
                "title": data["title"],
                "description": data["description"],
                "category": data["category"],
                "punishment": data.get("punishment"),
                "keywords": data.get("keywords", []),
                "old_law": {
                    "act": "Indian Penal Code, 1860",
                    "act_short": "IPC",
                    "section": ipc_section,
                },
            }
    return None


def lookup_crpc_section(section: str) -> dict[str, Any] | None:
    """Look up a CrPC section and return its details with BNSS mapping."""
    normalized = normalize_section_number(section)
    
    if normalized in CRPC_TO_BNSS_MAP:
        data = CRPC_TO_BNSS_MAP[normalized]
        return {
            "found": True,
            "act": "Code of Criminal Procedure, 1973",
            "act_short": "CrPC",
            "section": normalized,
            "title": data["title"],
            "description": data["description"],
            "category": data["category"],
            "keywords": data.get("keywords", []),
            "new_law": {
                "act": "Bharatiya Nagarik Suraksha Sanhita, 2023",
                "act_short": "BNSS",
                "section": data["bnss_section"],
            },
        }
    return None


def lookup_bnss_section(section: str) -> dict[str, Any] | None:
    """Look up a BNSS section and return its details with CrPC mapping."""
    normalized = normalize_section_number(section)
    
    for crpc_section, data in CRPC_TO_BNSS_MAP.items():
        if data["bnss_section"] == normalized:
            return {
                "found": True,
                "act": "Bharatiya Nagarik Suraksha Sanhita, 2023",
                "act_short": "BNSS",
                "section": normalized,
                "title": data["title"],
                "description": data["description"],
                "category": data["category"],
                "keywords": data.get("keywords", []),
                "old_law": {
                    "act": "Code of Criminal Procedure, 1973",
                    "act_short": "CrPC",
                    "section": crpc_section,
                },
            }
    return None


_ACT_SHORT_PATTERNS: dict[str, str] = {
    "BSA": "BSA",
    "BHARATIYA SAKSHYA": "BSA",
    "EVIDENCE ACT": "BSA",
    "IEA": "BSA",
    "TPA": "TPA",
    "TRANSFER OF PROPERTY": "TPA",
    "POCSO": "POCSO",
    "PROTECTION OF CHILDREN": "POCSO",
    "PWDVA": "PWDVA",
    "DOMESTIC VIOLENCE": "PWDVA",
    "RTI": "RTI",
    "RIGHT TO INFORMATION": "RTI",
    "IDA": "IDA",
    "INDUSTRIAL DISPUTES": "IDA",
    "ICA": "ICA",
    "CONTRACT ACT": "ICA",
    "INDIAN CONTRACT": "ICA",
    "CPA": "CPA",
    "CONSUMER PROTECTION": "CPA",
    "NI ACT": "NI Act",
    "NEGOTIABLE INSTRUMENTS": "NI Act",
    "IT ACT": "IT Act",
    "INFORMATION TECHNOLOGY": "IT Act",
    "COI": "COI",
    "CONSTITUTION": "COI",
    "ARTICLE": "COI",
}


def lookup_other_act_section(act_short: str, section: str) -> dict[str, Any] | None:
    """Look up a section in OTHER_IMPORTANT_LAWS by act short name and section number."""
    section_upper = section.strip().upper()
    for act_info in OTHER_IMPORTANT_LAWS:
        if act_info["act_short"].upper() == act_short.upper():
            for sec_key, sec_data in act_info["sections"].items():
                if sec_key.upper() == section_upper:
                    return {
                        "found": True,
                        "act": act_info["act_name"],
                        "act_short": act_info["act_short"],
                        "section": sec_key,
                        "title": sec_data["title"],
                        "description": sec_data["description"],
                        "keywords": sec_data.get("keywords", []),
                    }
    return None


def lookup_section(query: str) -> dict[str, Any] | None:
    """
    Universal section lookup that tries to identify the act and section.
    Supports formats like:
    - "IPC 420", "Section 420 IPC", "420 IPC"
    - "BNS 318", "Section 318 BNS"
    - "CrPC 154", "Section 154 CrPC"
    - "BNSS 173"
    - "RTI Section 7", "POCSO 3", "Article 21"
    - "Section 138 NI Act", "IT Act 66"
    """
    query = query.strip().upper()

    ipc_match = re.search(r"(?:IPC|INDIAN\s*PENAL\s*CODE)\s*(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)", query)
    if not ipc_match:
        ipc_match = re.search(r"(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)\s*(?:OF\s*)?(?:IPC|INDIAN\s*PENAL\s*CODE)", query)
    if ipc_match:
        return lookup_ipc_section(ipc_match.group(1))

    bns_match = re.search(r"(?:BNS|BHARATIYA\s*NYAYA\s*SANHITA)\s*(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)", query)
    if not bns_match:
        bns_match = re.search(r"(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)\s*(?:OF\s*)?(?:BNS|BHARATIYA\s*NYAYA\s*SANHITA)", query)
    if bns_match:
        return lookup_bns_section(bns_match.group(1))

    crpc_match = re.search(r"(?:CRPC|CR\.?P\.?C\.?|CRIMINAL\s*PROCEDURE\s*CODE)\s*(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)", query)
    if not crpc_match:
        crpc_match = re.search(r"(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)\s*(?:OF\s*)?(?:CRPC|CR\.?P\.?C\.?)", query)
    if crpc_match:
        return lookup_crpc_section(crpc_match.group(1))

    bnss_match = re.search(r"(?:BNSS|BHARATIYA\s*NAGARIK\s*SURAKSHA\s*SANHITA)\s*(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)", query)
    if not bnss_match:
        bnss_match = re.search(r"(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)\s*(?:OF\s*)?(?:BNSS)", query)
    if bnss_match:
        return lookup_bnss_section(bnss_match.group(1))

    for pattern, act_short in _ACT_SHORT_PATTERNS.items():
        if pattern in query:
            sec_match = re.search(r"(?:SECTION|SEC\.?|S\.?|ARTICLE|ART\.?)?\s*(\d+[A-Z]?(?:\([A-Z0-9]+\))?)", query)
            if sec_match:
                result = lookup_other_act_section(act_short, sec_match.group(1))
                if result:
                    return result

    section_only = re.search(r"(?:SECTION|SEC\.?|S\.?)?\s*(\d+[A-Z]?)", query)
    if section_only:
        section = section_only.group(1)
        result = lookup_ipc_section(section)
        if result:
            return result
        result = lookup_crpc_section(section)
        if result:
            return result

    return None


def search_law_by_topic(topic: str, limit: int = 5) -> list[dict[str, Any]]:
    """
    Search for relevant law sections by topic/keyword.
    """
    topic_lower = topic.lower()
    results = []
    
    for ipc_section, data in IPC_TO_BNS_MAP.items():
        keywords = data.get("keywords", [])
        title_lower = data["title"].lower()
        desc_lower = data["description"].lower()
        
        score = 0
        for kw in keywords:
            if kw in topic_lower:
                score += 2
        if any(word in title_lower for word in topic_lower.split()):
            score += 1
        if any(word in desc_lower for word in topic_lower.split()):
            score += 0.5
        
        if score > 0:
            results.append({
                "score": score,
                "act": "IPC",
                "section": ipc_section,
                "title": data["title"],
                "description": data["description"],
                "bns_section": data["bns_section"],
            })
    
    for crpc_section, data in CRPC_TO_BNSS_MAP.items():
        keywords = data.get("keywords", [])
        title_lower = data["title"].lower()
        desc_lower = data["description"].lower()
        
        score = 0
        for kw in keywords:
            if kw in topic_lower:
                score += 2
        if any(word in title_lower for word in topic_lower.split()):
            score += 1
        if any(word in desc_lower for word in topic_lower.split()):
            score += 0.5
        
        if score > 0:
            results.append({
                "score": score,
                "act": "CrPC",
                "section": crpc_section,
                "title": data["title"],
                "description": data["description"],
                "bnss_section": data["bnss_section"],
            })
    
    for act_info in OTHER_IMPORTANT_LAWS:
        for section, data in act_info["sections"].items():
            keywords = data.get("keywords", [])
            title_lower = data["title"].lower()
            desc_lower = data["description"].lower()
            
            score = 0
            for kw in keywords:
                if kw in topic_lower:
                    score += 2
            if any(word in title_lower for word in topic_lower.split()):
                score += 1
            if any(word in desc_lower for word in topic_lower.split()):
                score += 0.5
            
            if score > 0:
                results.append({
                    "score": score,
                    "act": act_info["act_short"],
                    "act_full": act_info["act_name"],
                    "section": section,
                    "title": data["title"],
                    "description": data["description"],
                })
    
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


def get_all_law_entries() -> list[dict[str, Any]]:
    """Get all law entries for indexing."""
    entries = []
    
    for section, data in IPC_TO_BNS_MAP.items():
        entries.append({
            "id": f"ipc-{section}",
            "act": "Indian Penal Code, 1860",
            "act_short": "IPC",
            "section": section,
            "title": data["title"],
            "text": f"Section {section} IPC - {data['title']}: {data['description']}",
            "description": data["description"],
            "category": data["category"],
            "punishment": data.get("punishment"),
            "keywords": data.get("keywords", []),
            "bns_section": data["bns_section"],
        })
    
    for section, data in CRPC_TO_BNSS_MAP.items():
        entries.append({
            "id": f"crpc-{section}",
            "act": "Code of Criminal Procedure, 1973",
            "act_short": "CrPC",
            "section": section,
            "title": data["title"],
            "text": f"Section {section} CrPC - {data['title']}: {data['description']}",
            "description": data["description"],
            "category": data["category"],
            "keywords": data.get("keywords", []),
            "bnss_section": data["bnss_section"],
        })
    
    for act_info in OTHER_IMPORTANT_LAWS:
        for section, data in act_info["sections"].items():
            entries.append({
                "id": f"{act_info['act_short'].lower().replace(' ', '-')}-{section}",
                "act": act_info["act_name"],
                "act_short": act_info["act_short"],
                "section": section,
                "title": data["title"],
                "text": f"Section {section} {act_info['act_short']} - {data['title']}: {data['description']}",
                "description": data["description"],
                "keywords": data.get("keywords", []),
            })
    
    return entries


def index_law_knowledge() -> int:
    """One-time indexing job: embed every law entry and upsert into the shared
    `law_sections` table. Run via scripts/index_law_kb.py using the service-role
    client — this is admin/setup work, never called from a request handler."""
    service = _db.get_service_client()
    entries = get_all_law_entries()
    if not entries:
        return 0

    texts = [entry["text"] for entry in entries]
    embeddings = embed_texts(texts)
    if not embeddings:
        raise RuntimeError("Embedding provider unavailable — set HUGGINGFACE_API_KEY before indexing.")

    rows = [
        {
            "id": entry["id"],
            "act": entry["act"],
            "act_short": entry["act_short"],
            "section": entry["section"],
            "title": entry["title"],
            "description": entry["description"],
            "category": entry.get("category"),
            "punishment": entry.get("punishment"),
            "embedding": embeddings[i],
        }
        for i, entry in enumerate(entries)
    ]
    for i in range(0, len(rows), 200):
        service.table("law_sections").upsert(rows[i:i + 200]).execute()
    return len(entries)


def semantic_search_laws(query: str, limit: int = 5) -> list[dict[str, Any]]:
    """Semantic search over the pre-indexed law knowledge base. Read-only,
    uses the public (anon-key) client — law_sections is public-read reference
    data, not scoped to any one user."""
    embedding = embed_text(query)
    if not embedding:
        return []

    public = _db.get_public_client()
    result = public.rpc("match_law_sections", {"query_embedding": embedding, "match_count": limit}).execute()

    output = []
    for row in result.data:
        output.append({
            "text": f"Section {row['section']} {row['act_short']} - {row['title']}: {row['description']}",
            "metadata": {
                "act": row["act"], "act_short": row["act_short"], "section": row["section"],
                "title": row["title"], "category": row.get("category"), "punishment": row.get("punishment"),
            },
            "relevance_score": row.get("similarity", 0.0),
        })

    return output
