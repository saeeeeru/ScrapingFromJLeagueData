import os
import time
import urllib.request
from datetime import datetime
from tqdm import tqdm

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.select import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

def get_goal_ranking_df(URL = "https://data.j-league.or.jp/SFTD08/search?selectFlag=0&competition_frames=1&competition_year_from=&competition_year_to=&goals_from=20&goals_to="):
    data = urllib.request.urlopen(URL)
    soup = BeautifulSoup(data, "lxml")

    table = soup.find_all("table", id="search_result")[0]
    c_list = [el.get_text() for el in table.find_all("th")]

    n_cols = len(c_list)
    values_array = np.array(
        [
            el.get_text()
            .replace("\t", "")
            .replace("\r", "")
            .replace("\n", "")
            .replace("\u3000", "")
            for el in table.find_all("td")
            if el.get_text() != ""
        ]
    ).reshape(-1, n_cols)

    df = pd.DataFrame(columns=c_list, data=values_array)

    df.to_csv(
        os.path.join(os.getcwd(), "data", "goal_ranking", f"{datetime.now()}_goal_ranking.csv"),
        index=False,
    )

def get_participate_df(driver, team, data_dir, n_move):
    # 最初に戻るには2回押す
    wait = WebDriverWait(driver, 10)
    for i in range(n_move-1):
        prev_btn = wait.until(EC.element_to_be_clickable((By.ID, 'prevBtnB')))
        prev_btn.click()
    
    df_list = list()
    for i in range(n_move):
        time.sleep(10)
        table = BeautifulSoup(driver.page_source, "html.parser").find('table', id='search_result')
        # カラム
        c_list = [th.text for th in table.find_all('th', 'bg wd02')]
        # 試合情報
        c_data_array = np.array(
            [td.text.replace('\n', '').replace('\t', '') 
             for td in table.find_all(lambda tag: tag.name == 'td' and tag.get('class') == ['bg'])]
        ).reshape(-1, len(c_list))
        # 出場記録
        v_array = np.array(
            [td.text.replace('\n','').replace('\t','')
                 for td in table.find_all(lambda tag: tag.name == 'td' and ((tag.get('class') == ['bd-l'])or(tag.get('class') == None)))]
        ).reshape(-1, len(c_list))
        # 選手インデックス
        index_list = [th.text.replace('\u3000','') for th in table.find_all('th', 'bd-l sort al-l name-c')]
        # dataframe化
        df = pd.DataFrame(index=index_list, columns=c_list, data=v_array)
        df_list.append(df)
        
        if i != n_move-1:
            next_btn = wait.until(EC.element_to_be_clickable((By.ID, 'nextBtnB')))
            next_btn.click()
    
    # 横に結合
    df = pd.concat(df_list, axis=1)
    
    # ローカル保存
    df.to_csv(os.path.join(data_dir, f'{team}.csv'))

def scrape_each_team(driver, wait, data_dir, n_move):
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)

    # team_selector = Select(wait.until(EC.element_located_to_be_selected((By.NAME, "team_id"))))
    time.sleep(10)
    team_selector = Select(driver.find_element_by_name("team_id"))

    team_list = [option.text for option in team_selector.options if option.text != '▼']
    
    for team in tqdm(team_list):
        time.sleep(10)
        team_selector = Select(driver.find_element_by_name("team_id"))
        team_selector.select_by_visible_text(team)
        
        search_btn = wait.until(EC.element_to_be_clickable((By.ID, 'search')))
        search_btn.click()

        get_participate_df(driver, team, data_dir, n_move)

        home_btn = wait.until(EC.element_to_be_clickable((By.ID, 'back')))
        home_btn.click()

def scrape_all(URL = 'https://data.j-league.or.jp/SFPR01/'):
    DRIVER_PATH = os.path.join(os.getcwd(), 'chromedriver')
    data_dir = os.path.join('data')

    # Seleniumをあらゆる環境で起動させるChromeオプション
    options = Options()
    options.add_argument('--disable-gpu');
    options.add_argument('--disable-extensions')
    options.add_argument('--proxy-server="direct://"')
    options.add_argument('--proxy-bypass-list=*')
    options.add_argument('--start-maximized')
    options.add_argument('--headless')

    # ブラウザの起動
    driver = webdriver.Chrome(executable_path=DRIVER_PATH, chrome_options=options)

    # url
    driver.get(URL)

    year_selector = Select(driver.find_element_by_name("competition_year"))
    year_list = [option.text for option in year_selector.options if option.text != '▼']

    wait = WebDriverWait(driver, 30)
    
    for year in year_list[3:-1]:
        time.sleep(10)
        year_selector = Select(driver.find_element_by_name("competition_year"))
        print(year)
        year_selector.select_by_visible_text(year)

        # competition_selector = Select(wait.until(EC.element_located_to_be_selected((By.NAME, "competition_frame_id"))))
        time.sleep(10)
        competition_selector = Select(driver.find_element_by_name( "competition_frame_id"))

        competition_list = [option.text for option in competition_selector.options if option.text != '▼' and option.text.endswith('リーグ')]
        
        competition = 'Ｊ２リーグ'
        competition_selector.select_by_visible_text(competition)

        if competition=='Ｊ１リーグ' and year in ['2015年', '2016年']:
            time.sleep(10)
            stage_selector = Select(driver.find_element_by_name('competition_id'))
            stage_list = [option.text for option in stage_selector.options if option.text != '▼']
            for stage in stage_list:
                time.sleep(10)
                stage_selector = Select(driver.find_element_by_name('competition_id'))
                stage_selector.select_by_visible_text(stage)
                data_dir_tmp = os.path.join(data_dir, year, competition, stage)
                scrape_each_team(driver, wait, data_dir_tmp, n_move=2)

        else:
            data_dir_tmp = os.path.join(data_dir, year, competition)
            scrape_each_team(driver, wait, data_dir_tmp, n_move=4 if competition=='Ｊ２リーグ' else 3)
            

def main():
    # ゴールランキング
    # get_goal_ranking_df()

    # 出場時間
    scrape_all()

if __name__ == "__main__":
    main()
