const { DateTime } = require("luxon");

module.exports = function(eleventyConfig) {
  eleventyConfig.addPassthroughCopy("src/css");
  eleventyConfig.addPassthroughCopy("src/img");
  eleventyConfig.addPassthroughCopy("src/audio");
  eleventyConfig.addPassthroughCopy("src/*.html");
  eleventyConfig.addPassthroughCopy("src/*.pdf");
  eleventyConfig.addPassthroughCopy("src/*.jpg");
  eleventyConfig.addPassthroughCopy("src/*.png");
  eleventyConfig.addPassthroughCopy("src/talks");
  eleventyConfig.addPassthroughCopy("src/ttwife");

  eleventyConfig.addFilter("date", (dateObj, format) => {
    return DateTime.fromJSDate(dateObj, { zone: "utc" }).toFormat(format || "MMMM d, yyyy");
  });

  eleventyConfig.addCollection("posts", function(collectionApi) {
    return collectionApi.getFilteredByGlob("src/blog/*.md").sort((a, b) => b.date - a.date);
  });

  eleventyConfig.addFilter("dirUrl", function(url) {
    return url.substring(0, url.lastIndexOf("/") + 1);
  });

  eleventyConfig.addFilter("getPrevNext", function(collection, currentUrl) {
    const idx = collection.findIndex(p => p.url === currentUrl);
    return {
      prev: idx < collection.length - 1 ? collection[idx + 1] : null,
      next: idx > 0 ? collection[idx - 1] : null
    };
  });

  return {
    dir: {
      input: "src",
      output: "_site",
      includes: "_includes"
    },
    markdownTemplateEngine: "njk",
    htmlTemplateEngine: "njk"
  };
};
