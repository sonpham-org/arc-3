"""a119 Temporal Booking -- assign overlapping equipped tasks without room conflicts."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CALENDAR,ROOM,TASK_A,TASK_B,EQUIP,TIME,CURSOR,CONFLICT,MISSING=0,8,7,12,14,10,9,13,6,4
BAD=15
STARTS=(0,2,4,1,5,7);DUR=(3,3,2,4,3,2);NEED=(0,1,2,0,2,1);HAS=(0,1,2)
LEVELS=[
 {"name":"Book Room","seq":(1,)},{"name":"Select Task","seq":(2,)},
 {"name":"Shift Interval","seq":(3,1)},{"name":"Detect Conflict","seq":(1,2,3,4,2)},
 {"name":"Match Equipment","seq":(1,3,2,1,4,3,2)},{"name":"Temporal Booking","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 rooms,shifts,cursor,conflicts,missing,history,snapshot=s;r=list(rooms);sh=list(shifts)
 if a==1:r[cursor]=(r[cursor]+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%6;history=(history+(2,))[-8:]
 elif a==3:sh[cursor]=(sh[cursor]+1)%3;history=(history+(3,))[-8:]
 elif a==4:
  conflicts=0
  for i in range(6):
   ai=STARTS[i]+sh[i];bi=ai+DUR[i]
   for j in range(i+1,6):
    aj=STARTS[j]+sh[j];bj=aj+DUR[j];conflicts+=int(r[i]==r[j] and max(ai,aj)<min(bi,bj))
  missing=sum(int(NEED[i]!=HAS[r[i]]) for i in range(6));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(r),tuple(sh),cursor,conflicts,missing,history)
 return tuple(r),tuple(sh),cursor,conflicts,missing,history,snapshot
for x in LEVELS:
 s=((0,1,2,0,2,1),(0,0,0,0,0,0),0,1,0,(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=CALENDAR
  for room in range(3):
   y=13+room*14;f[y:y+10,7:57]=ROOM;f[y+3:y+7,8:12]=EQUIP
  for i,(room,shift) in enumerate(zip(g.rooms,g.shifts)):
   x=14+(STARTS[i]+shift)*4;y=14+room*14;w=DUR[i]*4;f[y:y+8,x:min(57,x+w)]=TASK_A if i%2==0 else TASK_B
   if i==g.cursor:f[y-3:y,x:min(57,x+w)]=CURSOR
  f[54:58,8:8+g.conflicts*7]=CONFLICT;f[7:10,8:8+g.missing*7]=MISSING
  if g.bad:f[1:4,18:46]=BAD
  return f
class A119(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a119",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.rooms,self.shifts,self.cursor,self.conflicts,self.missing,self.history,self.snapshot=((0,1,2,0,2,1),(0,0,0,0,0,0),0,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.rooms,self.shifts,self.cursor,self.conflicts,self.missing,self.history,self.snapshot=advance((self.rooms,self.shifts,self.cursor,self.conflicts,self.missing,self.history,self.snapshot),a)
  elif a==6:
   if (self.rooms,self.shifts,self.cursor,self.conflicts,self.missing,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
