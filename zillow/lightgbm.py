####################################
# lightgbm.py
# use lightgbm to predict the log error in Zillow
# data competition 
# Yun Zhang 06/05/2017
####################################

# import package
import pandas as pd
import numpy as np
import lightgbm as lgb
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import (roc_curve, auc, accuracy_score)
from sklearn.model_selection import GridSearchCV
import gc

################################
# data preprocessing
################################

# load transaction data
# extract the sale month
transaction=pd.read_csv('../input/train_2016.csv', parse_dates=["transactiondate"]);
transaction['sale_month']=transaction['transactiondate'].apply(lambda x: (x.to_datetime()).month)
transaction['sale_month'].astype(int,inplace=True)
transaction.drop(['transactiondate'],axis=1,inplace=True)

############################
# load properties data
properties_2016=pd.read_csv('../input/properties_2016.csv',low_memory=False);
# categorize features
id_feature=['airconditioningtypeid','architecturalstyletypeid','buildingclasstypeid',
           'buildingqualitytypeid','decktypeid','hashottuborspa','heatingorsystemtypeid',
           'pooltypeid10','pooltypeid2','pooltypeid7','propertylandusetypeid',
            'storytypeid','typeconstructiontypeid','fireplaceflag','taxdelinquencyflag',
            'taxdelinquencyyear']
cnt_feature=['bathroomcnt','bedroomcnt','calculatedbathnbr','fireplacecnt','fullbathcnt',
            'garagecarcnt','garagetotalsqft','poolcnt','roomcnt','threequarterbathnbr',
            'unitcnt','yearbuilt','numberofstories','assessmentyear']
size_feature=['basementsqft','finishedfloor1squarefeet','calculatedfinishedsquarefeet',
             'finishedsquarefeet12','finishedsquarefeet13','finishedsquarefeet15',
              'finishedsquarefeet50','finishedsquarefeet6','lotsizesquarefeet',
             'poolsizesum','yardbuildingsqft17','yardbuildingsqft26','structuretaxvaluedollarcnt','taxvaluedollarcnt',
             'landtaxvaluedollarcnt','taxamount','latitude','longitude']
location_feature=['fips','propertycountylandusecode','rawcensustractandblock',
                 'regionidcity','regionidcounty','regionidneighborhood','regionidzip','censustractandblock']
str_feature=['propertyzoningdesc','propertycountylandusecode']

# delete all object data
# value for these feature are constant
dtype_df = properties_2016.dtypes.reset_index()
dtype_df.columns = ["Feature", "Column Type"]
dtype_df.groupby("Column Type").aggregate('count').reset_index()
properties_2016.drop(dtype_df[dtype_df['Column Type']=='object']['Feature'].values.tolist(),axis=1,inplace=True)
del dtype_df

############################
# check the missing percentage
missing_df = properties_2016.isnull().sum(axis=0).reset_index()
missing_df.columns = ['column_name', 'missing_count']
missing_df = missing_df.ix[missing_df['missing_count']>0]
missing_df = missing_df.sort_values(by='missing_count')
missing_df['missing_rate']=missing_df['missing_count']/2985217
cutoff=1
# drop feature missing rate>cutoff
properties_2016.drop(missing_df[(missing_df.missing_rate>=cutoff)].column_name.values.tolist(),
                    axis=1,inplace=True)

del missing_df

#################################
# categorize the left feature
feature_left=properties_2016.columns.tolist()
id_feature_left=list()
cnt_feature_left=list()
size_feature_left=list()
location_feature_left=list()
for x in feature_left:
    if x in id_feature:
      id_feature_left.append(x)
    elif x in cnt_feature:
      cnt_feature_left.append(x)
    elif x in size_feature:
      size_feature_left.append(x)
    elif x in location_feature:
      location_feature_left.append(x)

# fill missing values
# for id_feature, fill the missing values with most frequent value
# for cnt_feature, fill the missing values with median value
# for size_feature, fill the missing values with mean values
# for location_feature, fill the missing values with the nearest values
fill_missing_value=dict()
# for id_feature
for x in id_feature_left:
    fill_missing_value[x]=0#properties_2016[x].value_counts().index.tolist()[0]
# for cnt_feature
for x in cnt_feature_left:
    fill_missing_value[x]=0#properties_2016[x].median()
# for size_feature
for x in size_feature_left:
    fill_missing_value[x]=0#properties_2016[x].mean()
# for size_feature
for x in location_feature_left:
    fill_missing_value[x]=0#properties_2016[x].value_counts().index.tolist()[0]
for x in fill_missing_value:
   properties_2016[x].fillna(fill_missing_value[x],inplace=True)
del fill_missing_value,id_feature_left,cnt_feature_left,size_feature_left,location_feature_left

######################################################
# for location_feature
# regionidcounty and fips is the same to represent the county keep fips
# censustractandblock is drop as to be the same as rawcensustractandblock.
# regionidneighborhood >60% missing rate is droped
#properties_2016.drop(['regionidcounty','regionidneighborhood','censustractandblock'],axis=1,inplace=True)

#############################################
# divide 1000000 for longitude and latitude
#properties_2016['longitude']=properties_2016['longitude']/1000000;
#properties_2016['latitude']=properties_2016['latitude']/1000000;

#############################################
# add new features
# 1. tax per living area = tax amount/calculatedfinishedsquarefeet
# 2. tax per living area2 =tax amount/finishedsquarefeet12
# 3. tax per lot size=taxamount/lotsizesquarefeet
properties_2016['tax_per_liv_area']=properties_2016['taxamount']/properties_2016['calculatedfinishedsquarefeet'];
properties_2016['tax_per_liv_area2']=properties_2016['taxamount']/properties_2016['finishedsquarefeet12'];
properties_2016['tax_per_lot_size']=properties_2016['taxamount']/properties_2016['lotsizesquarefeet'];

        
###########################################
#dummy_feature=['airconditioningtypeid','buildingqualitytypeid','fips','heatingorsystemtypeid',
#              'propertylandusetypeid']
#for x in dummy_feature:
#    a=pd.get_dummies(properties_2016[x])
#    print(a.shape)
#    a.columns=[x+'_'+str(n) for n in a.columns.tolist()]
#    properties_2016=pd.concat([properties_2016,a], axis=1)
#print("new properties shape:",properties_2016.shape)
#properties_2016.drop(dummy_feature,axis=1,inplace=True)
# del dummy_feature,a

############################################
# normalize all features except dummy feature
features=properties_2016.columns.tolist()
features.remove('parcelid')
for x in features:
    feature_max=properties_2016[x].max()
    feature_min=properties_2016[x].min()
    if(feature_max==feature_min):
        print(x,'max==min, cannot normalize, max=',feature_max)
        print('This feature only has one value, so will be dropped.')
        properties_2016.drop(x,axis=1,inplace=True)
    else:
        properties_2016[x]=(properties_2016[x]-feature_min)/(feature_max-feature_min)

########################################
# get the train and test data
train_df=transaction.merge(properties_2016,on='parcelid',how='left')
train_df.set_index('parcelid',inplace=True)
train_df['sale_month']=train_df['sale_month']/12;
X_train=train_df.iloc[:,1:]
y_train=train_df['logerror']

sample = pd.read_csv('../input/sample_submission.csv')
sample['parcelid'] = sample['ParcelId']
df_test = sample.merge(properties_2016, on='parcelid', how='left')
# still need the sale month as input
train_feature=properties_2016.columns.tolist()
X_test=df_test[train_feature]
X_test.set_index('parcelid',inplace=True)
# predict with linear regress
X_test['sale_month']=10/12
X_test=X_test[X_train.columns.tolist()]

del transaction,properties_2016,df_test,train_df

################################
# model refinement gridsearchcv
################################
# Set params
# Scores ~0.784 (without tuning and early stopping) 
print('start optimize lightgbm')
# Create parameters to search
gridParams = {
    'learning_rate': [0.008,0.012,0.016,0.020]
    'n_estimators': [10,20,40],
    'num_leaves': [10,20,40,60,80],
    }

# To view the default model params:
y_predict=clf.predict(X_train)
print('train score:',np.mean(abs(y_predict-y_train)))

# Create the grid
grid = GridSearchCV(clf, gridParams, scoring='neg_mean_absolute_error',verbose=1, cv=3, n_jobs=-1)
# Run the grid
grid.fit(X_train, y_train)

print('Best parameters found by grid search are:', grid.best_params_)
print(grid.cv_results_)

################################
# model train
################################
clf=lgb.LGBMRegressor(boosting_type='gbdt',max_depth=-1,n_estimators=50,num_leaves=60,seed=500
,learning_rate=0.012)
clf.fit(X_train,y_train)
y_predict=clf.predict(X_train)
print('train score:',np.mean(abs(y_predict-y_train)))
# Plot importance
lgb.plot_importance(clf)
plt.savefig('feature_importance.eps',bbox_inches='tight')
print('finish training')

################################
# output prediction
################################

output=pd.read_csv('../input/sample_submission.csv')
output.set_index('ParcelId',inplace=True)
clf.reset_parameter({"num_threads":1})
for mon in [10,11,12]:
    X_test['sale_month']=mon/12;
    p_test = clf.predict(X_test)
    output['2016'+str(mon)]=p_test
print('start to output')
output.to_csv('lgb.csv', float_format='%.4f')
print('finish output')




