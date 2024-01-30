
function changeTheme() {
    var theme = document.getElementById("themeSelect").value;
    fetch(`/set_theme/${theme}`)
        .then(response => {
            if (response.ok) {
                // Update the theme immediately without reloading the page
                var link = theme === "Superhero" ? 
                           "https://bootswatch.com/5/css/bootstrap.min.css" : 
                           `https://bootswatch.com/5/${theme}/bootstrap.min.css`;
                document.getElementById("bootstrapCSS").href = link;
            }
        })
        .catch(error => console.error('Error:', error));
}
