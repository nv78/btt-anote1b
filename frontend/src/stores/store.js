import { combineReducers } from 'redux';
import { configureStore } from '@reduxjs/toolkit';
import storage from 'redux-persist/lib/storage';
import {
    FLUSH,
    PAUSE,
    PERSIST,
    PURGE,
    REGISTER,
    REHYDRATE,
    persistReducer,
    persistStore
} from 'redux-persist';
import { checkAndUpdateSchema } from './schema';
import datasetsReducer from '../redux/DatasetSlice';

const persistConfig = {
    key: 'root',
    storage,
};

const rootReducer = combineReducers({
    datasets: datasetsReducer,
});

const persistedReducer = persistReducer(persistConfig, rootReducer);

export const store = configureStore({
    reducer: persistedReducer,
    middleware: (getDefaultMiddleware) =>
        getDefaultMiddleware({
            serializableCheck: {
                ignoredActions: [FLUSH, REHYDRATE, PAUSE, PERSIST, PURGE, REGISTER],
            },
        }),
});

const initialSchema = {
    datasets: true,
};

checkAndUpdateSchema(initialSchema, store);

export const persistor = persistStore(store);
