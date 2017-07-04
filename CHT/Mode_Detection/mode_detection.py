# -*- coding: utf-8 -*-
import numpy
import math
import pickle
import datetime

def d(p1, p2):
	# p1, p2 = [long, lat]
	if p1 == p2: # special case: p1 = p2
		return 0.0
	# end of if
	#print '1'
	# Great-circle distance
	phi_s = math.radians(p1[1])
	phi_f = math.radians(p2[1])

	delta_lampda = math.radians(p1[0]) - math.radians(p2[0])
	delta_phi = phi_s - phi_f
	#print '2'
	delta_sigma = 2 * math.asin(math.sqrt( math.sin(delta_phi / 2) * math.sin(delta_phi / 2) + math.cos(phi_s) * math.cos(phi_f) * math.sin(delta_lampda / 2) * math.sin(delta_lampda / 2)))
	return delta_sigma * 6378137 # unit (meter)
	
def route_distance(route,start,end,bus_info):
	distance = 0
	for i in range(start+1,end+1,1):
		x = (float(bus_info[route][i][2]),float(bus_info[route][i][3])) 
		y = (float(bus_info[route][i-1][2]),float(bus_info[route][i-1][3]))
		distance = distance + d(x,y)
	return distance


def bus_trip_detection(rid2user,user2rid,route2rid,bus_route,SpeedDis,speed_threshold=5,match_number=2,merge_type='distance'):
	bus_trip = []
	for route in route2rid.keys():
		candidate_users = set()
		for r in route2rid[route]:
			candidate_users = candidate_users | rid2user[r]

		match = {} 
		route_set = set(route2rid[route])
		for u in candidate_users:
			match[u] = []
			for i in range(0,len(user2rid[u]),1):
				tra_set = set(user2rid[u][i][0])
				if len(tra_set & route_set)!=0:
					match[u].append(i)
							
		
		for u in match.keys():
			stay_index = [i for i,data in enumerate(user2rid[u],0) if data[5]==1]
			for i in range(1,len(stay_index),1):
				seg = [user2rid[u][x] for x in match[u] if (x>=stay_index[i-1]) & (x<=stay_index[i])]
				if len(seg) > 0:
					s_rid = set(seg[0][0]) & route_set
					e_rid = set(seg[-1][0]) & route_set
					if (len(s_rid)!=0) & (len(e_rid)!=0):
						s_rid = list(s_rid)[-1]
						e_rid = list(e_rid)[0]
						s_index = [stop_index for (stop_index,x) in enumerate(route2rid[route],0) if x == s_rid][0]
						e_index = [stop_index for (stop_index,x) in enumerate(route2rid[route],0) if x == e_rid][-1]


						if (e_index - s_index) >= match_number:
							s_point = seg[0]
							e_point = seg[-1]

							travel_time = e_point[1] - s_point[2]
							travel_time = travel_time/3600.0 # hour
							distance = route_distance(route,s_index,e_index,bus_route)
							distance = distance/1000.0 #km
							if (travel_time > 0) & (distance > 0):
								est_speed = float(distance)/travel_time
								hour = int(datetime.datetime.fromtimestamp(s_point[2]).strftime('%H'))
								try:
									true_speed = SpeedDis[route][hour]
								except:
									true_speed = SpeedDis[hour]
								if abs(est_speed - true_speed) <= speed_threshold:
									bus_trip.append([u,s_point[2],e_point[1],route,s_index,e_index])
	
	# merge overlap bus trips
	bus_trip_ = sorted(bus_trip,key=lambda x:x[0]) 
	u = bus_trip[0][0]
	overlap_bus_trip = []
	l = []
	for row in bus_trip:
		if u == row[0]:
			l.append([row[1],row[2],row[3:],row[0]])
		else:
			l = sorted(l,key=lambda x:x[0]) 
			r = list(merge(l))
			overlap_bus_trip.extend(r)
			l = []
			l.append([row[1],row[2],row[3:],row[0]])
			u = row[0]		
	overlap_bus_trip.extend(r)
	
	# select the longest trip as result
	longest_bus_trip = []
	for n,row in enumerate(overlap_bus_trip,0):
		t = []
		for route,start,end in row[2]:
			pass_stop = end - start + 1
			distance = route_distance(route,start,end,bus_route)
			t.append([distance,pass_stop,route,start,end])
		if merge_type == 'distance':
			t = sorted(t,reverse=True,key=lambda x:x[0])
		elif merge_type == 'stop':
			t = sorted(t,reverse=True,key=lambda x:x[1])
			
		longest_bus_trip.append([row[3],row[0],row[1],t[0][2],t[0][3],t[0][4]])	
	
	return longest_bus_trip
	
def merge(times):
	saved = [times[0][0],times[0][1],[times[0][2]],times[0][3]]
	for st, en, r,u in times:
		if st <= saved[1]:
			saved[1] = max(saved[1], en)
			saved[2].append(r)
                
		else:
			yield tuple(saved)
			saved[0] = st
			saved[1] = en
			saved[2] = [r]
			saved[3] = u
	yield tuple(saved)
    
	
	
def find_the_closest_train_no(travel_time,start_time,end_time,time_threshold):
    for train_no,depart_time,arrival_time in travel_time:
        start_diff = abs(start_time - depart_time)
        end_diff = abs(end_time - arrival_time)
        if (start_diff <= time_threshold*60) & (end_diff <= time_threshold*60):
            return train_no
    return 'empty'

def HSR_trip_detection(user_data,travel_time,stations,HSR_ref_sys,time_threshold=5,stay_time=10):
    #user_data: [(imsi,start_time,end_time,lon,lat)...]
    #travel_time: dict, travel_time[i][j] = [(train_no,start_time,end_time)]
    #stations: stations[station_id][station_name and position]
    #HSR_ref_sys: dict, HSR_reference_system, HSR_ref_sys[station_id] = [(lon,lat)...]
    #time_threshold: integer, 5 (minutes)
    #stay_time: integer, 10 (minutes)

    HSR_trips = []
    imsi = user_data[0][0]
    stay_index = [i for i,data in enumerate(user_data,0) if (data[2]-data[1]) >=stay_time*60 ]
    
    for i in range(1,len(stay_index),1):
        seg = user_data[stay_index[i-1]:stay_index[i]+1]
        if len(seg) > 0:
            # spatail match
            match_station = []
            for row in seg:
                for station in stations.keys():
                    for ref_tower in HSR_ref_sys[station]:
                        if (ref_tower[0] == row[3]) & (ref_tower[1] == row[4]):
                            match_station.append( [station,row] )

            # temporal match
            if len(match_station) > 1:  # at least two stations ( depart and arrival ) 
                for trip_num in range(1,len(match_station),1):
                    depart_station = match_station[trip_num-1][0]
                    arrival_station = match_station[trip_num][0]
                    if depart_station != arrival_station: # depart station and arrival station are difference
                        start_time = match_station[trip_num-1][1][2]
                        end_time = match_station[trip_num][1][1]
                        train_no = find_the_closest_train_no(travel_time[depart_station][arrival_station],start_time,end_time,time_threshold)
                        if train_no != 'empty':
                            HSR_trips.append( [imsi,start_time,end_time,train_no,depart_station,arrival_station])

    return HSR_trips