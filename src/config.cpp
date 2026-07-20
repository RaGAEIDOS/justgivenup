#include "config.h"
#include "log.h"
#include <cstdio>
#include <windows.h>
#include <shlobj.h>
#include <shlwapi.h>

Config::Config() {
    wchar_t appdata[MAX_PATH];
    if (SUCCEEDED(SHGetFolderPathW(NULL, CSIDL_APPDATA, NULL, 0, appdata))) {
        CreateDirectoryW(appdata, NULL);
        PathAppendW(appdata, L"JustGivenUp");
        CreateDirectoryW(appdata, NULL);
        PathAppendW(appdata, L"config.json");
        char pathA[MAX_PATH];
        WideCharToMultiByte(CP_UTF8, 0, appdata, -1, pathA, MAX_PATH, NULL, NULL);
        _path = pathA;

        FILE* f = fopen(_path.c_str(), "r");
        if (f) {
            fseek(f, 0, SEEK_END);
            long sz = ftell(f);
            fseek(f, 0, SEEK_SET);
            std::string buf((size_t)sz, '\0');
            fread(buf.data(), 1, sz, f);
            fclose(f);

            try {
                json j = json::parse(buf);
                _cfg = from_json(j);
                return;
            } catch (...) {
                Log::instance().error("Config parse failed, using defaults");
            }
        }
    }
    load_defaults();
    save();
}

void Config::load_defaults() {
    _cfg.interval_seconds = 3;
    _cfg.nsfw_threshold = 0.45f;
    _cfg.cooldown_seconds = 10;
    _cfg.dashboard_port = 8081;

    // Auto-detect all common browsers
    _cfg.browsers = {
        "chrome.exe","firefox.exe","msedge.exe","brave.exe","opera.exe",
        "vivaldi.exe","tor.exe","tor-browser.exe","waterfox.exe","palemoon.exe",
        "maxthon.exe","slimjet.exe","yandexbrowser.exe","comodo_dragon.exe",
        "epic.exe","centbrowser.exe","coc_coc_browser.exe","avast_browser.exe",
        "avira_browser.exe","avg_browser.exe","qutebrowser.exe","lynx.exe",
        "netscape.exe","seamonkey.exe","k-meleon.exe","browser.exe","iexplore.exe",
        "msedge.exe","msedgewebview2.exe"
    };

    // ── Massive Whitelist: skip detection entirely ──
    _cfg.whitelist_skip = {
        // Learning platforms
        "udemy","coursera","edx","edx.org","khanacademy","udacity","skillshare",
        "pluralsight","codecademy","freecodecamp","mit ocw","mitopencourseware",
        "stanford online","stanford.edu","harvard.edu","mit.edu","oxford.edu",
        "cambridge.org","brilliant","datacamp","treehouse","lynda","linkedin learning",
        "masterclass","domestika","creativelive","teachable","thinkific","learnworlds",
        "kajabi","podia","mighty networks","circle.so","disco.co","pathwright",
        "iversity","openlearning","futurelearn","classcentral","academicearth",
        "openculture","open2study","alison","saylor","edureka","simplilearn",
        "greatlearning","upgrad","guvi","codingninjas","scaler","interviewbit",
        "codingblocks","hackerearth","codechef","topcoder","geeksforgeeks",
        "w3schools","tutorialspoint","programiz","javatpoint","sololearn",
        "codewars","exercism","odin project","theodinproject","fullstackopen",
        "hyperskill","jetbrains academy","stepik","practicum","hexlet",
        "code.org","scratch.mit.edu","codingbat","codility","coderbyte",

        // YouTube & Video Learning
        "youtube","youtu.be","youtube.com","youtube-nocookie.com",
        "يوتيوب","يوتيب",
        "youtubeeducation","teachertube","schooltube","khanacademy",
        "ted.com","tedx","ted ed",

        // Docs & Reference
        "stackoverflow","stackexchange","github","gitlab","bitbucket",
        "codepen","replit","codesandbox","glitch","jsfiddle","jsbin",
        "leetcode","hackerrank","codewars","exercism",
        "google scholar","scholar.google","researchgate","academia.edu",
        "pubmed","ncbi.nlm.nih.gov","jstor","ieeexplore","sciencedirect",
        "springer","wiley","tandfonline","sagepub","acm.org",
        "wikipedia","wikibooks","wikiversity","wikihow","wikidata",
        "merriam-webster","dictionary","thesaurus","britannica",
        "reference.com","infoplease","bartleby","chegg","quizlet",
        "sparknotes","cliffsnotes","bookrags","gradesaver","shmoop",

        // Development & Tech
        "stackoverflow","github","gitlab","bitbucket","codepen",
        "replit","codesandbox","glitch","jsfiddle","jsbin",
        "leetcode","hackerrank","topcoder","codeforces","codewars",
        "exercism","hackerearth","codechef","atcoder",
        "dev.to","medium.com","hashnode","digitalocean","linode",
        "aws.amazon.com","aws console","azure.microsoft","cloud.google",
        "learn.microsoft","docs.microsoft","developer.mozilla","mdn",
        "canonical","ubuntu","debian","redhat","archlinux",
        "kernel.org","sourceforge","launchpad","gnu.org",
        "python.org","pypi.org","npmjs.com","rubygems","crates.io",
        "nuget.org","maven.org","gradle.org","docker.com","kubernetes",
        "grafana","prometheus","jenkins","travis-ci","circleci",
        "readthedocs","gitbook","notion.so","obsidian.md",
        "roamresearch","logseq","remnote","foambubble",

        // Productivity & Communication
        "zoom","zoom.us","teams","microsoft teams","microsoft.com",
        "office.com","office365","outlook","outlook.com","live.com",
        "hotmail","gmail","mail.google","protonmail","proton.me",
        "tutanota","fastmail","zoho mail","yahoo mail",
        "google meet","meet.google","webex","cisco webex","gotomeeting",
        "slack","discord","discord.com","telegram","signal.org",
        "whatsapp","whatsapp.com","messenger","m.me",
        "google calendar","calendar.google","calendly","cal.com",
        "todoist","trello","asana","jira","confluence","basecamp",
        "monday.com","notion","evernote","onenote","keep.google",
        "google drive","drive.google","dropbox","box.com",
        "icloud","onedrive","mega.nz","sync.com","pcloud",

        // Education (specific courses)
        "100 days of code","python bootcamp","web development bootcamp",
        "javascript course","react course","node course","machine learning",
        "deep learning","data science","artificial intelligence",
        "computer science","programming","coding","software engineering",
        "math","calculus","linear algebra","statistics","probability",
        "physics","chemistry","biology","history","literature",
        "economics","accounting","finance","marketing","business",
        "toeic","ielts","toefl","gmat","gre","sat","act",

        // Google Apps & Classroom
        "google classroom","classroom.google","canvas","blackboard",
        "moodle","schoology","brightspace","edmodo","seesaw",
        "nearpod","peardeck","quizizz","kahoot","blooket","gimkit",
        "flippity","padlet","jamboard","miro","figma","figjam",
        "google colab","colab.research","jupyter","deepnote","kaggle",
        "google docs","docs.google","sheets.google","slides.google",
        "forms.google","sites.google",

        // Academic search
        "google scholar","semanticscholar","crossref","doaj","base-search",
        "core.ac.uk","zenodo","osf.io","figshare","datadryad",
        "orcid","scopus","web of science","dimensions.ai",
        "pubmed","pmc","medrxiv","biorxiv","arxiv","hal.archives",
        "cnrs","inserm","inria","mpg.de","cern","nasa.gov",
        "nasa","esa","space.com","spacenews",
    };

    // ── Whitelist: lenient detection (higher threshold, e.g. 0.75) ──
    _cfg.whitelist_lenient = {
        "reddit","reddit.com","twitter","x.com","facebook","instagram",
        "tumblr","pinterest","imgur","flickr","deviantart","behance",
        "dribbble","artstation","500px","unsplash","pexels",
        "news","cnn","bbc","nytimes","theguardian","reuters",
        "apnews","npr","bloomberg","forbes","wsj","washingtonpost",
    };

    // ── Blacklist: instant tab-close (proxy/porn/streaming/.ru) ──
    _cfg.blacklist_kill = {
        // Proxy/unblock sites
        "proxy","proxysite","proxy-site","crocoproxy","croxyproxy",
        "croxy","unblock","unblocked","unblocker","bypass","bypasser",
        "vpn","vpnbook","freevpn","protonvpn","nordvpn","expressvpn",
        "torrent","torrents","bittorrent","utorrent","webtorrent",
        "youtube-unblocked","youtubeunblocked","youtube-unlock",
        "youtubeunlock","unlock youtube","unblock youtube",
        "anonymox","hide.me","hidemyass","hideman","vpn gate",
        "tunnelbear","windscribe","hotspot shield","betternet",
        "psiphon","ultrasurf","freenet","i2p","tor project",
        "whatsmyip","hidemyip","myip","ipaddress","dns leak",

        // Russian domains
        "ok.ru","vk.ru","mail.ru","my.mail","yandex.ru","rutube.ru","rambler.ru",
        "rbc.ru","ria.ru","tass.ru","iz.ru","kp.ru","lenta.ru",
        "gazeta.ru","kommersant.ru","fontanka.ru","mk.ru",
        ".ru ",".ru/",".ru?","ru.wikipedia",".su ","my.mail.ru",
        // Russian explicit content keywords
        "лолита","лолит",

        // Adult content (comprehensive)
        "xnxx","xhamster","pornhub","xvideos","redtube","youporn",
        "tube8","spankbang","porntube","eporner","porndude",
        "porn.com","adult","xxx","sex","porno","porntrex",
        "hclips","tktube","pornkai","pornhd","vporn","xmovies",
        "porn300","pornwhite","pornrabbit","pornstars","pornpic",
        "nudevista","nudetube","sextv","sexvideo","sexfilm",
        "onlyfans","fansly","patreon","mym","fanhouse",
        "stripchat","chaturbate","livejasmin","cam4","bongacams",
        "myfreecams","flingster","omegle","chatrandom","chatroulette",

        // Streaming (non-learning video)
        "netflix","hulu","disney+","disneyplus","hbomax","max.com",
        "prime video","amazon.com/video","paramount+","peacocktv",
        "apple tv","appletv","crunchyroll","funimation","hidive",
        "twitch.tv","kick.com","trovo","dlive","streamlabs",
        "dailymotion","dmotion",
        "spotify","deezer","tidal","pandora",
        "9anime","aniwatch","gogoanime","zoro.to","animepahe",
    };
}

AppConfig Config::from_json(const json& j) {
    AppConfig c;
    if (j.contains("interval_seconds")) c.interval_seconds = j["interval_seconds"];
    if (j.contains("nsfw_threshold")) c.nsfw_threshold = j["nsfw_threshold"];
    if (j.contains("cooldown_seconds")) c.cooldown_seconds = j["cooldown_seconds"];
    if (j.contains("dashboard_port")) c.dashboard_port = j["dashboard_port"];
    if (j.contains("browsers")) c.browsers = j["browsers"].get<std::vector<std::string>>();
    if (j.contains("whitelist_skip")) c.whitelist_skip = j["whitelist_skip"].get<std::vector<std::string>>();
    if (j.contains("whitelist_lenient")) c.whitelist_lenient = j["whitelist_lenient"].get<std::vector<std::string>>();
    if (j.contains("blacklist_kill")) c.blacklist_kill = j["blacklist_kill"].get<std::vector<std::string>>();
    if (j.contains("lock_until")) c.lock_until = j["lock_until"];
    if (j.contains("lock_seal")) c.lock_seal = j["lock_seal"];
    if (j.contains("setup_complete")) c.setup_complete = j["setup_complete"];
    if (j.contains("language")) c.language = j["language"];
    if (j.contains("user_name")) c.user_name = j["user_name"];
    if (j.contains("user_work")) c.user_work = j["user_work"];
    if (j.contains("user_picture")) c.user_picture = j["user_picture"];
    return c;
}

json Config::to_json(const AppConfig& c) {
    return {
        {"interval_seconds", c.interval_seconds},
        {"nsfw_threshold", c.nsfw_threshold},
        {"cooldown_seconds", c.cooldown_seconds},
        {"dashboard_port", c.dashboard_port},
        {"browsers", c.browsers},
        {"whitelist_skip", c.whitelist_skip},
        {"whitelist_lenient", c.whitelist_lenient},
        {"blacklist_kill", c.blacklist_kill},
        {"lock_until", c.lock_until},
        {"lock_seal", c.lock_seal},
        {"setup_complete", c.setup_complete},
        {"language", c.language},
        {"user_name", c.user_name},
        {"user_work", c.user_work},
        {"user_picture", c.user_picture},
    };
}

void Config::save() {
    FILE* f = fopen(_path.c_str(), "w");
    if (f) {
        std::string data = to_json(_cfg).dump(4);
        fwrite(data.data(), 1, data.size(), f);
        fflush(f);
        fclose(f);
    }
}
