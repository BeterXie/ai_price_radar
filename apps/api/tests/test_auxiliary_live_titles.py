import pytest
from app.services.classifier import classify_product


@pytest.mark.parametrize('title,category,expected', [
    ('Team 5x ｜下极品gmail邮箱｜长效用到号死', 'team', 'chatgpt-business'),
    ('长效 1x team gmail邮箱【质保1小时】不质保降智、429和负载', 'team', 'chatgpt-business'),
    ('1X Team 有5h限制 用到空间炸 | G邮箱 | 账密+2FA | 质保4H', 'team', 'chatgpt-business'),
    ('Team10X ｜真二车｜gmail邮箱 ｜下午15:00下车', '自营', 'chatgpt-business'),
    ('二车 23：30踢人 10xteam 额度500-1000刀 gm邮箱', 'G', 'chatgpt-business'),
    ('Team10X【速刷多轮】【gmail邮箱 500-1000刀】到21点', 'team', 'chatgpt-business'),
    ('【iCloud注册的接马free】可以邮箱收件，RT老号，账号-密码-2fa格式， 不是谷歌号看清下单', 'free', 'chatgpt-account'),
    ('G Plus 未接马半价资格号三个月（可以改绑自己的邮箱）', 'G', 'chatgpt-account'),
    ('mail邮箱（不是gmail不是gmail）', '账号类', 'email-account'),
    ('Outlook 邮箱 非 Gmail', '邮箱', 'email-outlook'),
    ('Google邮箱接马印尼实卡接马API', '接马服务', 'verification-google'),
    ('Google邮箱接马印尼实卡接马api无限换号到成功', '接马codex、pp和提链cdk', 'verification-google'),
    ('Google 接马-美区 【长效60天】全系谷歌邮箱 不售后', '谷歌，油管接马', 'verification-google'),
    ('iCloud 隐私邮箱 无限接收验证码', '邮箱', 'email-icloud'),
    ('Team Gmail 企业邮箱账号', '邮箱', 'email-gmail'),
    ('【稳定可用】iCloud隐私邮箱|不能分裂|只保证能用openAI', '邮箱', 'email-icloud'),
    ('韩国Tiktok | 满月白', '社媒账号', 'social-media-account'),
    ('【台湾】 ID账号-可下币安等APP/独享/质保', 'Apple ID', 'apple-id-account'),
    ('【港区】ID账号-可下APP/独享/质保/gmail后缀非谷歌邮箱', '苹果账号', 'apple-id-account'),
    ('USA +1双向成品号', 'Telegram账号', 'social-media-account'),
    ('485954 验证试用0美元卡', '虚拟卡', 'virtual-card'),
    ('ios礼品卡充值自助订阅Claude pro', '礼品卡', 'gift-card'),
    ('Gmail教育邮箱租用 30天 GMail Edu 独享稳定', '邮箱', 'email-education'),
    ('小红书 · 千百天高权重长效老号 · 国际版（密码/SID/UID）', '社媒账号', 'social-media-account'),
    ('【GitHub 18-19号新注册账号】Gmail邮箱注册 | 带2FA+恢复码 | 到手即可换绑', '账号', None),
])
def test_auxiliary_live_title_regressions(title, category, expected):
    assert classify_product(title, category).slug == expected
