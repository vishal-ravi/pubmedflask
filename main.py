import requests
import re
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from flask import Flask, request, render_template, redirect,session


app = Flask(__name__)

app.secret_key = "e191da2ae5ffc9a60d2db18993862f65"

# Replace with your actual API key
api_key = "7c13496fb6f075b0cf97f52998b5f92a9108"

# Base URL for PubMed API
base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Define the keywords to check (can be an empty list initially)
keywords_to_check = []


@app.route("/", methods=["GET", "POST"])
def index():
    pmids = None
    pmcid_results = {}  # Use a dictionary to store PMCID results for each PMID
    title_results = {}  # Use a dictionary to store title results for each PMID
    full_text_links = {}  # Use a dictionary to store full text links for each PMID
    publication_types = {}  # Use a dictionary to store publication types for each PMID
    exclude_messages = {}  # Use a dictionary to store exclusion messages for each PMID
    keyword_results = {}  # Use a dictionary to store keyword results for each PMID

    # Initialize show_loader to False
    show_loader = False

    # Initialize an empty dictionary

    if request.method == "POST":
        pmids_input = request.form["pmids"]
        keywords = request.form["keywords"].split(',')
        session["keywords"] = keywords
        # Split the input PMIDs by commas and clean them
        pmids = [pmid.strip() for pmid in pmids_input.split(',')]

        # Show the loader while fetching data
        show_loader = True


        for pmid in pmids:
            pmcid = get_pmcid(pmid)
            title = get_title(pmid)
            full_text_link = get_full_text_link(pmid)
            publication_type = get_publication_type(pmid)


            # Check if publication type should trigger exclusion
            exclude_message = None
            if should_exclude(publication_type):
                exclude_message = "This article is excluded due to its publication type."

            # Fetch the abstract
            abstract = get_abstract(pmid, keywords)

            # Check keywords in the abstract and get relevant sentences
            keyword_results[pmid] = get_sentences_with_exact_keywords(
                abstract, keywords)

            # Store the results in dictionaries
            pmcid_results[pmid] = pmcid
            title_results[pmid] = title
            full_text_links[pmid] = full_text_link
            publication_types[pmid] = publication_type
            exclude_messages[pmid] = exclude_message

        # Hide the loader after data is fetched
        show_loader = False

    return render_template(
        "index.html",
        pmids=pmids,
        pmcid_results=pmcid_results,
        title_results=title_results,
        full_text_links=full_text_links,
        publication_types=publication_types,
        exclude_messages=exclude_messages,
        keyword_results=keyword_results,
        show_loader=show_loader,
    )

def get_sentences_with_exact_keywords(abstract, keywords):
    try:
        sentences = abstract.split(". ")
        found_sentences = []

        for sentence in sentences:
            for keyword in keywords:
                keyword = keyword.strip()
                words_in_sentence = sentence.split()
                if keyword.lower() in [word.lower() for word in words_in_sentence]:
                    found_sentences.append((keyword, sentence))
                    break  # Stop checking keywords in this sentence if one is found

        return found_sentences if found_sentences else [("No keyword found", "")]
    except Exception as e:
        return [(f"Error: {str(e)}", "")]


def get_pmcid(pmid):
    # Construct the API request URL to fetch article metadata
    api_url = f"{base_url}/efetch.fcgi?db=pubmed&retmode=xml&id={pmid}&api_key={api_key}"

    # Make the API request
    response = requests.get(api_url)

    if response.status_code == 200:
        xml_content = response.text
        root = ET.fromstring(xml_content)

        # Find the PMCID if available
        pmcid_element = root.find(".//ArticleId[@IdType='pmc']")

        if pmcid_element is not None:
            pmcid = pmcid_element.text
            return pmcid  # Return only the PMCID without "PMID:"
        else:
            return "PMCID Not Found"
    else:
        return "Error: Unable to fetch PMCID"


def get_title(pmid):
    api_url = f"{base_url}/esummary.fcgi?db=pubmed&id={pmid}&api_key={api_key}"
    response = requests.get(api_url)

    if response.status_code == 200:
        xml_content = response.text
        root = ET.fromstring(xml_content)

        title_element = root.find(".//Item[@Name='Title']")
        if title_element is not None:
            return title_element.text
        else:
            return "Title Not Found"
    else:
        return "Error"


def get_full_text_link(pmid):
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
    response = requests.get(pubmed_url)

    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')

        link_item = soup.find("a", class_="link-item dialog-focus")
        if link_item:
            return link_item.get('href')

    return "Link Not Found"


def get_publication_type(pmid):
    api_url = f"{base_url}/efetch.fcgi?db=pubmed&retmode=xml&id={pmid}&api_key={api_key}"
    response = requests.get(api_url)

    if response.status_code == 200:
        xml_content = response.text
        root = ET.fromstring(xml_content)

        publication_type_elements = root.findall(".//PublicationType")
        publication_types = [elem.text for elem in publication_type_elements]

        return ", ".join(publication_types) if publication_types else "Publication Type Not Found"
    else:
        return "Error"


def should_exclude(publication_type):
    # Define the publication types to exclude
    excluded_types = ['Review', 'Clinical Trial', 'Patient Study']

    # Check if any of the excluded types match the publication type
    for excluded_type in excluded_types:
        if excluded_type in publication_type:
            return True

    return False


def get_abstract(pmid, keywords):
    # Construct the URL to fetch the article's HTML page
    article_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"

    # Make the request to the article's page
    article_response = requests.get(article_url)

    if article_response.status_code == 200:
        soup = BeautifulSoup(article_response.text, "html.parser")
        abstract_element = soup.find("div", class_="abstract", id="abstract")

        if abstract_element:
            # Extract all paragraphs within the abstract
            paragraphs = abstract_element.find_all("p")

            if paragraphs:
                # Create a dictionary to store sentences by keyword
                keyword_sentences = {keyword: [] for keyword in keywords}

                for paragraph in paragraphs:
                    # Get the text of the paragraph
                    paragraph_text = paragraph.get_text(strip=True)

                    # Check each keyword individually
                    for keyword in keywords:
                        if keyword.lower() in paragraph_text.lower():
                            # Append the sentence to the corresponding keyword
                            keyword_sentences[keyword].append(paragraph_text)

                # Initialize the abstract text
                abstract_text = ""

                # Generate the abstract text with headings and numbered sentences
                for keyword, sentences in keyword_sentences.items():
                    if sentences:
                        abstract_text += f"{keyword}:\n"
                        for i, sentence in enumerate(sentences, start=1):
                            abstract_text += f"{i}. {sentence}\n"

                return abstract_text.strip()

    return "Abstract Not Found"


def get_sentences_with_exact_keywords(abstract, keywords):
    sentences = abstract.split(". ")
    found_sentences = []

    for sentence in sentences:
        for keyword in keywords:
            keyword = keyword.strip()
            words_in_sentence = sentence.split()
            if keyword.lower() in [word.lower() for word in words_in_sentence]:
                found_sentences.append((keyword, sentence))
                break  # Stop checking keywords in this sentence if one is found

    return found_sentences if found_sentences else [("No keyword found", "")]

@app.route("/view-complete-article/<pmcid>", methods=["GET"])
def view_complete_article(pmcid):
    if pmcid:
        # Construct the PDF URL
        pdf_url = f'https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/'
        return redirect(pdf_url)
    else:
        return "PMC ID is required."


@app.route("/view_full_text/<pmid>", methods=["GET"])
def view_full_text(pmid):
    keywords = session.get("keywords")
    if pmid:
        # Get the PMCID
        pmcid = get_pmcid(pmid)

        # Construct the URL to fetch the full text content
        full_text_url = f'https://www.ncbi.nlm.nih.gov/research/bionlp/RESTful/pmcoa.cgi/BioC_xml/{pmcid}/unicode'

        # Make the request to the full text URL
        full_text_response = requests.get(full_text_url)

        if full_text_response.status_code == 200:
            # Extract the content from the response
            full_text_content = full_text_response.text

            # Extract and display sentences related to keywords
            keyword_sentences = get_sentences_with_keywords(full_text_content, keywords, full_text_response, full_text_url)

            # Pass the keyword_sentences to the template
            keyword_counts = {keyword: {"count": len(sentences), "details": sentences} for keyword, sentences in
                              keyword_sentences.items()}

            return render_template("full_text.html", keywords=keywords,
                                   keyword_counts=keyword_counts)  # Pass keyword_counts to the template
        else:
            return "Error fetching full text content."
    else:
        return "PMC ID is required."


def get_sentences_with_keywords(full_text_content, keywords, full_text_response, full_text_url):
    keyword_sentences = {keyword: set() for keyword in keywords}
    keyword_counts = {keyword: 0 for keyword in keywords}  # Initialize keyword counts

    try:
        full_text_response = requests.get(full_text_url)
        # Parse the full text content as XML
        if full_text_response.status_code == 200:
            full_text_content = full_text_response.text
        root = ET.fromstring(full_text_content)

        # Define the desired mappings for section types and types
        desired_mappings = [
            {"section_type": "TITLE", "type": ["title", "front", "title_1", "title_2", "title_3"]},
            {"section_type": "SABSTRACT", "type": ["paragraph", "front", "abstract", "title_1", "title_2", "title_3"]},
            {"section_type": "INTRO", "type": ["paragraph", "front", "title_1", "title_2", "title_3"]},
            {"section_type": "METHODS", "type": ["paragraph", "front", "title_1", "title_2", "title_3"]},
            {"section_type": "CONCL", "type": ["paragraph", "front", "title_1", "title_2", "title_3"]},
            {"section_type": "DISCUSS", "type": ["paragraph", "front", "title_1", "title_2", "title_3"]},
        ]

        for keyword in keywords:
            keyword = keyword.strip()  # Remove leading/trailing spaces
            keyword_pattern = r'\b' + re.escape(keyword) + r'\b'  # Create a regex pattern for whole word matching
            for mapping in desired_mappings:
                section_type = mapping["section_type"]
                types = mapping["type"]

                for passage in root.findall(".//passage"):
                    section = passage.find(".//infon[@key='type']").text
                    text = passage.find(".//text").text
                    if section in types:

                        if re.search(keyword_pattern, text, re.IGNORECASE):
                            if text not in keyword_sentences[keyword]:
                                keyword_sentences[keyword].add(text)
                                # Increment the count for the keyword
                                keyword_counts[keyword] += 1

    except Exception as e:
        print(f"Error parsing XML content: {str(e)}")

    return keyword_sentences



if __name__ == "__main__":
    app.run(debug=True)
