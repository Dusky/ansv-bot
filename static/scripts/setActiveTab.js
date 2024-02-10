function changeTheme() {
    var theme = document.getElementById("themeSelect").value;
    fetch(`/set_theme/${theme}`)
        .then(response => {
            if (response.ok) {
                var link = `https://bootswatch.com/5/${theme}/bootstrap.min.css`;
                document.getElementById("bootstrapCSS").href = link;
            } else {
                console.error('Error in response:', response);
            }
        })
        .catch(error => console.error('Error:', error));
}
