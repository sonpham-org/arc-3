"""a190 Majority Decode -- wire five voters to tolerate any two sensor faults."""
from copy import deepcopy
from itertools import combinations
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,CHAMBER,SENSOR_ON,SENSOR_OFF,FAULT,CURSOR,WIRE,GATE,SAFE,ERROR=12,1,14,8,6,13,10,5,4,9
BAD=15
LEVELS=[
 {"name":"Toggle Voter","seq":(1,)},{"name":"Choose Sensor","seq":(2,)},
 {"name":"Move Faults","seq":(3,1)},{"name":"Test Majority","seq":(1,2,3,4,2)},
 {"name":"Repair Quorum","seq":(1,3,2,1,4,3,2)},{"name":"Majority Decode","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def audit(enabled):
 live=[i for i in range(5) if (enabled>>i)&1];cases=0;total=0
 for n in range(3):
  for faults in combinations(range(5),n):
   total+=1;bad=sum(i in faults for i in live);good=len(live)-bad;cases+=int(good>bad)
 return cases,total-cases
def advance(s,a):
 enabled,cursor,phase,safe,errors,history,snapshot=s
 if a==1:enabled^=1<<cursor;history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%5;history=(history+(2,))[-8:]
 elif a==3:phase=(phase+1)%10;history=(history+(3,))[-8:]
 elif a==4:safe,errors=audit(enabled);history=(history+(4,))[-8:]
 elif a==5:snapshot=(enabled,cursor,phase,safe,errors,history)
 return enabled,cursor,phase,safe,errors,history,snapshot
for q in LEVELS:
 s=(0b11111,0,0,16,0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=CHAMBER
  fault_a=g.phase%5;fault_b=(g.phase*2+2)%5
  for i in range(5):
   y=9+i*9;on=(g.enabled>>i)&1;f[y:y+7,8:17]=FAULT if i in (fault_a,fault_b) else SENSOR_ON if on else SENSOR_OFF;f[y+2:y+5,17:43]=WIRE if on else BG
   if i==g.cursor:f[y:y+7,5:8]=CURSOR
  f[22:44,43:56]=GATE;f[52:56,8:8+min(16,g.safe)*2]=SAFE;f[52:56,43:43+min(3,g.errors)*4]=ERROR
  if g.bad:f[1:4,18:46]=BAD
  return f
class A190(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a190",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.enabled,self.cursor,self.phase,self.safe,self.errors,self.history,self.snapshot=(0b11111,0,0,16,0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.enabled,self.cursor,self.phase,self.safe,self.errors,self.history,self.snapshot=advance((self.enabled,self.cursor,self.phase,self.safe,self.errors,self.history,self.snapshot),a)
  elif a==6:
   if (self.enabled,self.cursor,self.phase,self.safe,self.errors,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
