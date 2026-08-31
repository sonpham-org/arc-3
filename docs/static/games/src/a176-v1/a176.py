"""a176 Alias Breaker -- add one feature that minimally refines an invalid abstraction."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,LAB,OBSERVATION,SENSOR_A,SENSOR_B,SENSOR_C,ALIAS,SPLIT,MINIMAL,OVERFIT=13,8,7,12,14,10,6,4,11,9
BAD=15
LEVELS=[
 {"name":"Choose Sensor","seq":(1,)},{"name":"Select Alias","seq":(2,)},
 {"name":"Probe History","seq":(3,1)},{"name":"Split Pair","seq":(1,2,3,4,2)},
 {"name":"Preserve Other Merges","seq":(1,3,2,1,4,3,2)},{"name":"Alias Breaker","seq":(1,2,3,1,4,2,3,1,4,3)},
]
FEATURES=((0,0,1),(0,1,0),(1,0,0),(1,1,0),(0,0,0),(0,1,1))
def advance(s,a):
 sensor,cursor,history_probe,split,minimal,overfit,history,snapshot=s
 if a==1:sensor=(sensor+1)%3;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%3;history=(history+(2,))[-8:]
 elif a==3:history_probe=(history_probe+1)%4;history=(history+(3,))[-8:]
 elif a==4:
  pair=(cursor*2,cursor*2+1);split=int(FEATURES[pair[0]][sensor]!=FEATURES[pair[1]][sensor]);overfit=sum(int(FEATURES[i][sensor]!=FEATURES[i+1][sensor]) for i in range(0,6,2))-split;minimal=int(split and overfit==0);history=(history+(4,))[-8:]
 elif a==5:snapshot=(sensor,cursor,history_probe,split,minimal,overfit,history)
 return sensor,cursor,history_probe,split,minimal,overfit,history,snapshot
for q in LEVELS:
 s=(0,0,0,0,0,1,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=LAB;cols=(SENSOR_A,SENSOR_B,SENSOR_C)
  for i,feat in enumerate(FEATURES):
   x=10+(i%2)*28;y=10+(i//2)*15;f[y:y+11,x:x+18]=OBSERVATION;f[y+3:y+8,x+4:x+14]=cols[feat[g.sensor]]
   if i//2==g.cursor:f[y-3:y,x:x+18]=ALIAS
  f[54:58,8:28]=SPLIT if g.split else ALIAS;f[54:58,31:51]=MINIMAL if g.minimal else OVERFIT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A176(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a176",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.sensor,self.cursor,self.history_probe,self.split,self.minimal,self.overfit,self.history,self.snapshot=(0,0,0,0,0,1,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.sensor,self.cursor,self.history_probe,self.split,self.minimal,self.overfit,self.history,self.snapshot=advance((self.sensor,self.cursor,self.history_probe,self.split,self.minimal,self.overfit,self.history,self.snapshot),a)
  elif a==6:
   if (self.sensor,self.cursor,self.history_probe,self.split,self.minimal,self.overfit,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
