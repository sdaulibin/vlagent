package test;

import java.util.HashMap;
import java.util.Map;

import com.bqd.cms.Client;
import com.bqd.util.ServerMessage;


public class Test {

	public static void main(String[] args) {
		//Client client = new Client();
		Map<String,String> map = new HashMap<String,String>();
		try {
			
			
			/***************************普通上传接口文件上传开始******************************************
			
			
			Client client = new Client();
			//文件路径为目录
//			String path = "d://11";
 			//文件路径为文件路径
			String path = "d://11//";
			System.out.println(client.uploadByPathAndSerialNo(path,"20150908_aaadddd_0dd4","OL_PT"));
			/***************************普通文件接口文件上传结束*******************************************/
			
			/***************************自定义参数接口文件上传开始（贸金文件上传和特定参数信息上传）**********
			Client client = new Client();
			//文件所在目录
			String path = "d://11";
			Map<String,Map<String,String>> newMap = new HashMap<String,Map<String,String>>();
			
			//for(int i=1;i<3;i++){
				Map<String,String> sonMap = new HashMap<String,String>();
				sonMap.put("BUSI_FILE_TYPE", "7001005");
				sonMap.put("BUSI_FILE_PAGENUM", "1");
//				sonMap.put("RESERVE2", "哈哈");
//				sonMap.put("RESERVE1", "11111");
				
				//文件名称
				newMap.put( "支票复印.jpg", sonMap);
//				
				sonMap = new HashMap<String,String>();
				sonMap.put("BUSI_FILE_TYPE", "7001006");
				sonMap.put("BUSI_FILE_PAGENUM", "2");
				
//				sonMap.put("RESERVE2", "嘻嘻");
//				sonMap.put("RESERVE1", "2222");
				newMap.put("电汇凭证.jpg", sonMap);
				
		//	}
			
			System.out.println(client.uploadByPathAndSerialNo(path,"20150908_0019","TFS_YW",newMap,true));
			/***************************文件上传结束*******************************************/
			
			/****************************************普通批次更新接口开始****************************
			//map.put("fileName", "77FF790E-D97B-1074-A975-EF32DF59EB54");
			Client client = new Client(true);
			String fileName = "4B03AFB2-25E7-4887-C6E9-AB3B6D60AFAF";
			String result = client.updateByBusiSerial("20150908_0019","OL_PT","delete",fileName,"D:\\11\\电汇凭证.jpg");
			System.out.println(result);
			/*****************************************普通批次更新接口结束******************************/
			
			/*********************自定义参数更新接口开始(包含贸金、网银更新和其它自定义系统更新)****************************
			Client client = new Client(true);
			Map<String,Map<String,String>> newMap = new HashMap<String,Map<String,String>>();
			Map<String,String> sonMap = new HashMap<String,String>();
			
//			sonMap.put("BUSI_FILE_TYPE", "7001009");
//			sonMap.put("BUSI_FILE_PAGENUM", "7");
			sonMap.put("RESERVE1", "替换");
			sonMap.put("RESERVE2", "333");
			newMap.put("D:\\11\\电汇凭证.jpg", sonMap);
			
			
			//追加时使用
//			Map<String,String> sonMap1 = new HashMap<String,String>();
//			sonMap1.put("BUSI_FILE_TYPE", "7001010");
//			sonMap1.put("BUSI_FILE_PAGENUM", "6");
//			sonMap1.put("RESERVE1", "333");
//			sonMap1.put("RESERVE2", "444");
//			newMap.put("D:\\11\\白封.jpg", sonMap1);
			
			String fileName = "2374E123-DB91-1AA8-BEDD-E8CE47AEA6A4";
			client.uploadByPathAndSerialNo("D:/image/11/", "20230505_test_01", "GX_KHZL",null,true);
//			client.uploadByPathAndSerialNo("D:/image/11/", "20230505_test_002", "GX_KHZL", newMap, true);
//			client.uploadByPathAndSerialNo("D:/image/11/", "20230505_test_003", "GX_KHZL", "20230505", newMap, true);
//			client.uploadByPathAndSerialNo("D:/image/11/","87008750171111","GX_KHZL","20210702",newMap,true);//需指定具体的文件名
//			client.uploadByPathAndSerialNo(path,"20201116testwzh001","LOS_YW","LOS_YW",newMap,true);//需指定具体的文件名
//			client.uploadByPathAndSerialNo(path,"20230410test005","TESTTHREE",newMap,true);//不需指定具体的文件名，传路径下的所有文件
			String result = client.updateByBusiSerial("20150908_0019","OL_PT","delete",fileName,newMap,false);
			System.out.println(result);
			/*****************************************自定义参数更新接口结束******************************/
			
			/********************* Jar包上传可供控件查看的图片****************************
			Client client = new Client(true);
			
			// 目录树节点值  fileForm 
			// flag : 使用false
			String uploadResult = client.uploadForPlug("D:\\image\\11\\1.jpg", "20230526upload_test1","XYZ", "00001", false);
			
			
           /*********************************普通在线文件传输查询接口开始**********************************
			
			map.put("FILETITLE", "应用关联");
			Client client = new Client();
			String xml = client.queryByBusiSerialNo("20150908_hexin_00001","OL_PT",map);
			System.out.println("<><><><>" + xml);
			
			/*********************************普通在线文件传输查询接口结束*********************************/
			
			 /*********************************贸金在线文件传输查询接口开始**********************************
			//map.put("RESERVE1", "aaadddccc2");
			Client client = new Client();
			
			String xml = client.queryByBusiSerialNo("20150908_0016","TFS_YW",null,true);
			System.out.println("<><><><>" + xml);
			
			/*********************************贸金在线文件传输查询接口结束*********************************/
			
			
			 /*********************************普通下载接口开始*********************************
			Client client = new Client(true);
			map.put("FILETITLE", "应用关联");
			System.out.println(client.downloadByBusiSerialNo("D:\\123\\test","20150908_aaadddd_0dd4","OL_PT",map) + "----->>>>>>>");
			/*********************************普通下载接口结束*********************************/
			
			 /*********************************贸金下载接口开始*********************************
			Client client = new Client(true);
			map.put("FILETITLE", "支票复印");
			System.out.println(client.downloadByBusiSerialNo("D:\\123\\test","20150908_0019","TFS_YW",null,true) + "----->>>>>>>");
			/*********************************贸金下载接口结束*********************************/
			
			/*******************************普通删除接口开始（逻辑删除）****************************
			Client client = new Client();
			client.deleteByBusiSerialNo("20150908_0019","OL_PT");
			/******************************普通删除接口结束****************************************/
			
			/*******************************贸金删除接口开始（逻辑删除）****************************
			Client client = new Client();
			client.deleteByBusiSerialNo("20150908_0016","TFS_YW",true);
			/******************************贸金删除接口结束****************************************/
			
			/***************************核心文件上传开始******************************************
			Client client = new Client("upload");
			String path = "d://11";
			Map<String,Map<String,String>> newMap = new HashMap<String,Map<String,String>>();
			
			//for(int i=1;i<3;i++){
//				Map<String,String> sonMap = new HashMap<String,String>();
//				sonMap.put("BUSI_FILE_TYPE", "1001007");
//				sonMap.put("BUSI_FILE_PAGENUM", "1");
//				sonMap.put("RESERVE2", ");
				
				newMap.put( "支票复印.jpg", null);
				
//				sonMap = new HashMap<String,String>();
//				sonMap.put("BUSI_FILE_TYPE", "1001004");
//				sonMap.put("BUSI_FILE_PAGENUM", "2");
				
				newMap.put("应用关联", null);
		//	}
			
			System.out.println(client.uploadByPathAndSerialNo(path,"20150908_hexin_00001","OL_PT",newMap,false));
			/***************************核心文件上传结束*******************************************/
			
			/*********************************核心查询接口开始**********************************
			
			map.put("FILETITLE", "应用关联");
			Client client = new Client("download");
			String xml = client.queryByBusiSerialNo("20150908_hexin_00001","OL_PT",null);
			System.out.println("<><><><>" + xml);
			
			/*********************************核心查询接口结束*********************************/
			
			
			
			/*********************************核心根据流水号下载开始*********************************
			Client client = new Client("download");
			//map.put("RESERVE1", "aaadddccc2");
			System.out.println(client.downloadByBusiSerialNo("D:\\123\\test","20150908_hexin_00001","OL_PT",map));
			/*********************************根据流水号查询结束*********************************/
			
			
			//client.heightQueryExample();
			
			
		} catch (Exception e) {
			e.printStackTrace();
		}
		
	}
}
