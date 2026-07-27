/*
    subtitle search plugin
*/

// string GetTitle() 																-> get title for UI
// string GetVersion																-> get version for manage
// string GetDesc()																	-> get detail information
// string GetLoginTitle()															-> get title for login dialog
// string GetLoginDesc()															-> get desc for login dialog
// string ServerCheck(string User, string Pass) 									-> server check
// string ServerLogin(string User, string Pass) 									-> login
// string GetLanguages()															-> get support language
// string SubtitleWebSearch(string MovieFileName, dictionary MovieMetaData)			-> search subtitle by web browser
// array<dictionary> SubtitleSearch(string MovieFileName, dictionary MovieMetaData)	-> search subtitle
// string SubtitleDownload(string id)		

// https://www.angelcode.com/angelscript/

bool isDebug = false;

string MY_SVR_URL = "http://127.0.0.1:8085";  // your server url

array<array<string>> LangTable =
{
    { "en", "English" },
    { "zh-TW", "Chinese" },
    { "zh-CN", "Mandarin" },
    { "ja", "Japanese" },
    { "ko", "Korean" }
};
string GetTitle()
{
    return "我的歌词搜索器";
}
string GetVersion()
{
    return "0.2";
}
string GetDesc()
{
    return "访问本地服务，无需登录";
}
string GetLoginTitle()
{
    return "NoLogin";
}
string GetLoginDesc()
{
    return "无需登录";
}
string ServerCheck(string User, string Pass)
{
    return ServerLogin(User, Pass);
}
string ServerLogin(string User, string Pass)
{
    return "服务无需登录";
}
string GetLanguages()
{
    string lang_str = "";
    for (int i = 0, len = LangTable.size(); i < len; i++)
    {
        string lang = LangTable[i][0];
        if (not lang.isEmpty())
        {
            if (not lang_str.isEmpty()) lang_str += ", ";
            lang_str += lang;
        }
    }
    return lang_str;
}

string SubtitleWebSearch(string MovieFileName, dictionary MovieMetaData)
{
    // MovieMetaData 示例
    // fileName :   Example.2023.S01E02.1080p.WEB-DL.H264.AAC
    // fileExtension :   mp4
    // year :   2005
    // formatName :   WEB-DL
    // title :   Drawing Sword
    // seasonNumber :   2
    // audioCodec :   AAC
    // episodeNumber :   0
    // videoEncoder :   H264
    // resolution :   1080p
    string params = "filename=" + HostUrlEncode(MovieFileName);
    foreach( auto value, auto key : MovieMetaData )
    {
        params += "&";
        params += HostUrlEncode("meta_" + string(key)) + "=" + HostUrlEncode(string(value));
    }
    string final_url = MY_SVR_URL + "/search?" + params;
    return final_url;
}

array<dictionary> SubtitleSearch(string MovieFileName, dictionary MovieMetaData)
{
    string final_url = SubtitleWebSearch(MovieFileName, MovieMetaData);
    if (isDebug) {
        HostOpenConsole();
        HostPrintUTF8("SubtitleSearch " + final_url);
    }
    array<dictionary> search_map;
    // 返回json兼容射手网json
    // {
    //   "status": 0,
    //   "sub": {
    //     "subs": [ 
    //        {
    //          "filelist": [],
    //          "id": 123,
    //          "native_name": "名字",
    //          "filename": "名字.简.ass",
    //          "title": "",
    //          "format": "ass",
    //          "url": "",
    //          "lang": "zh-CN"} 
    //     ]
    //   }
    // }
    string search_str = HostUrlGetString(final_url);
    JsonReader json_reader;
    JsonValue json_root;
    if (json_reader.parse(search_str, json_root) && json_root.isObject())
    {
        JsonValue subtitles = json_root["sub"]["subs"];
        if (subtitles.isArray())
        {
            for(int i = 0, len = subtitles.size(); i < len; i++)
            {
                dictionary item;
                int id = subtitles[i]["id"].asInt();
                item["id"] = formatInt(id);
                item["title"] = subtitles[i]["native_name"].asString();
                item["fileName"] = subtitles[i]["filename"].asString();
                item["format"] = subtitles[i]["format"].asString();
                item["lang"] = subtitles[i]["lang"].asString();
                item["url"] = MY_SVR_URL + subtitles[i]["url"].asString();
                search_map.insertLast(item);
            }
        }
    }
    search_map.reverse();
    return search_map;
}
string SubtitleDownload(string id)
{
    string down_url = MY_SVR_URL + "/download?format=ass&id=" + HostUrlEncode(id);
    if (isDebug) {
        HostOpenConsole();
        HostPrintUTF8("SubtitleDownload " + down_url);
    }
    return HostUrlGetString(down_url);
}
