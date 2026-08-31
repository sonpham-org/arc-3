"""a052 Batch Furnace -- group compatible arrivals before a fixed-cost pulse."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FOUNDRY,BELT,MAT_A,MAT_B,FURNACE,SELECT,HEAT,COOL,BAD=12,8,9,10,14,4,11,13,6,15
LEVELS=[
 {"name":"First Arrival","seq":(1,)},{"name":"Select Batch","seq":(1,3)},
 {"name":"Fire Together","seq":(1,1,3,4)},{"name":"Cooling Window","seq":(1,2,1,3,4)},
 {"name":"Rare Material","seq":(1,2,1,1,3,4,2)},{"name":"Batch Furnace","seq":(1,1,2,1,3,4,2,1,3,4)},
]
def advance(s,a):
 bins,ages,cursor,selected,heat,batches,history,snapshot=s;b=list(bins);ag=list(ages)
 if a==1:b[cursor]=min(4,b[cursor]+1);ag[cursor]=0;cursor^=1;history=(history+(1,))[-8:]
 elif a==2:
  cursor^=1
  for i in range(2):
   if b[i]:ag[i]=min(5,ag[i]+1)
  history=(history+(2,))[-8:]
 elif a==3:selected^=1<<cursor;history=(history+(3,))[-8:]
 elif a==4:
  load=0
  for i in range(2):
   if selected&(1<<i):load+=b[i];b[i]=0;ag[i]=0
  heat=(heat+1)%5;batches=(batches+(min(4,load),))[-6:];selected=0;history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(b),tuple(ag),cursor,selected,heat,batches,history)
 return tuple(b),tuple(ag),cursor,selected,heat,batches,history,snapshot
for x in LEVELS:
 s=((0,0),(0,0),0,0,0,(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FOUNDRY;f[15:24,6:42]=BELT;f[36:45,6:42]=BELT
  for i,col in enumerate((MAT_A,MAT_B)):
   y=16+i*21
   for j in range(g.bins[i]):f[y:y+7,8+j*8:14+j*8]=col
   f[y-6:y-2,8:8+g.ages[i]*5]=COOL
   if g.selected&(1<<i):f[y+9:y+13,9:35]=SELECT
  f[13:48,44:58]=FURNACE;f[18:43,48:55]=HEAT
  for i,v in enumerate(g.batches):f[52:57,8+i*8:13+i*8]=HEAT if v>2 else SELECT
  if g.bad:f[1:4,18:46]=BAD
  return f
class A052(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a052",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.bins,self.ages,self.cursor,self.selected,self.heat,self.batches,self.history,self.snapshot=((0,0),(0,0),0,0,0,(),(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.bins,self.ages,self.cursor,self.selected,self.heat,self.batches,self.history,self.snapshot=advance((self.bins,self.ages,self.cursor,self.selected,self.heat,self.batches,self.history,self.snapshot),a)
  elif a==6:
   if (self.bins,self.ages,self.cursor,self.selected,self.heat,self.batches,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
