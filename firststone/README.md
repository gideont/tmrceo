# You are the first investor

A portable illustrated interactive essay for Firststone by Nexusflow. This is an article, not the earlier app prototype.

## Upload
Upload `index.html` from the release ZIP to any static website. All styling, illustrations, and interactive behavior are embedded in that one file. It also opens directly on your computer. No build, React runtime, account, analytics, database, external font, or network connection is required.

## Set the product link
Near the end of `index.html`, find `productUrl: ''` and replace the empty string with the public Firststone URL. Until a URL is supplied, the closing section honestly says the product link is coming soon and invites the reader to write their first step on the page. No fabricated product URL is used.

## Edit
`article.html` is the editable source with an image marker. `build.py` embeds the generated hero image into `index.html`. The release ZIP contains the ready-to-upload page, this guide, and image provenance. The `assets` directory retains the source image.

The article uses plain HTML, CSS, and JavaScript for portability. Charts are accessible SVG with live textual results. All numbers are illustrative scenarios, not forecasts or claims about reader outcomes. Reader input stays in the current page; downloading the personal note is optional. Reloading clears the note.

## Controls
- Time chart: choose weekly hours and see the annual total and allocation.
- Ownership chart: choose a scenario and change build cost, monthly income, savings, upkeep, and horizon. Hover, click, or keyboard-adjust the selected month to inspect cumulative cash and economic benefit.
- First-stone exercise: write a dream, useful outcome, and next action, then download a plain-text commitment.
- Print: use the print button or browser print command for a readable article with current chart settings.

The product-link setting should be filled before the article is published with a Firststone call to action. The article itself is ready to upload independently.
