"""a172 Minimal Memory -- store a sufficient statistic instead of recent events."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,STREAM,EVENT_A,EVENT_B,MEMORY,PARITY,LAST,SUM,GATE,ERROR=9,8,12,14,7,10,13,11,4,6
BAD=15
LEVELS=[
 {"name":"Read Event","seq":(1,)},{"name":"Change Statistic","seq":(2,)},
 {"name":"Reset Memory","seq":(3,1)},{"name":"Predict Gate","seq":(1,2,3,4,2)},
 {"name":"Keep Sufficient State","seq":(1,3,2,1,4,3,2)},{"name":"Minimal Memory","seq":(1,2,3,1,4,2,3,1,4,3)},
]
EVENTS=(1,0,1,1,0,1,0,0)
def advance(s,a):
 index,mode,memory,prediction,size,error,history,snapshot=s
 if a==1:
  e=EVENTS[index];index=(index+1)%len(EVENTS);memory=(memory+e)%4 if mode==0 else memory^e if mode==1 else e;history=(history+(1,))[-8:]
 elif a==2:mode=(mode+1)%3;history=(history+(2,))[-8:]
 elif a==3:memory=0;history=(history+(3,))[-8:]
 elif a==4:truth=sum(EVENTS[:index])%2;prediction=memory%2;size=1 if mode==1 else 2 if mode==2 else 3;error=int(prediction!=truth);history=(history+(4,))[-8:]
 elif a==5:snapshot=(index,mode,memory,prediction,size,error,history)
 return index,mode,memory,prediction,size,error,history,snapshot
for q in LEVELS:
 s=(0,1,0,0,1,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STREAM
  for i,e in enumerate(EVENTS):f[12:24,8+i*6:13+i*6]=EVENT_A if e else EVENT_B
  cols=(SUM,PARITY,LAST);f[31:48,12:28]=MEMORY;f[35:44,16:24]=cols[g.mode];f[31:48,38:54]=GATE if g.prediction else ERROR;f[54:58,8:8+g.size*12]=MEMORY;f[7:10,8:8+g.index*5]=STREAM
  if g.bad:f[1:4,18:46]=BAD
  return f
class A172(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a172",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.index,self.mode,self.memory,self.prediction,self.size,self.error,self.history,self.snapshot=(0,1,0,0,1,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.index,self.mode,self.memory,self.prediction,self.size,self.error,self.history,self.snapshot=advance((self.index,self.mode,self.memory,self.prediction,self.size,self.error,self.history,self.snapshot),a)
  elif a==6:
   if (self.index,self.mode,self.memory,self.prediction,self.size,self.error,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
