// 顺序加载脚本：不用 document.write（动态插入的脚本执行时文档已解析完，
// document.write 会清空页面），改用 onload 链式插入，并带 ?v= 规避 CEF 缓存
(function () {
    var V = "?v=" + Date.now();
    var files = ["js/util.js", "js/ribbon.js", "js/poll.js"];
    var i = 0;
    function next() {
        if (i >= files.length) return;
        var s = document.createElement("script");
        s.src = files[i++] + V;
        s.onload = next;
        s.onerror = next;
        (document.head || document.documentElement).appendChild(s);
    }
    next();
})();
