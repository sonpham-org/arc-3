"""q618 Escapement Grammar -- compose grouped gear messages and diagnose the fault they isolate."""
from copy import deepcopy
import numpy as np
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,TOWER,GEAR,TOKEN,GROUP,FAULT,CODE,BAD=3,12,11,15,14,10,9,8
LEVELS=[
 {"name":"First Group","message":(1,2,4),"fault":0},{"name":"Nested Gear","message":(2,3,4,1),"fault":1},
 {"name":"Relay Phrase","message":(1,2,4,3,4),"fault":2},{"name":"Fault Contrast","message":(3,1,4,2,3,4),"fault":3},
 {"name":"Composed Weight","message":(1,3,2,4,1,4),"fault":2},{"name":"Escapement Grammar","message":(2,1,4,3,2,4,1,4),"fault":1}]
def compose(message):
 stack=[]
 for a in message:
  if a in (1,2,3):stack.append(a)
  elif len(stack)>=2:b=stack.pop();c=stack.pop();stack.append((c+2*b)%4)
 return tuple(stack)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[5:59,4:60]=TOWER
  for i,v in enumerate(g.stack[-6:]):f[11+i*6:16+i*6,9:9+v*11]=GROUP if v==0 else TOKEN
  f[13:39,42:55]=GEAR;f[48:52,8:8+g.fault*11]=FAULT;f[54:58,8:8+(sum(g.stack)%5)*9]=CODE
  if g.bad:f[61:64,21:43]=BAD
  return f
class Q618(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.stack=[];self.history=[];self.fault=0;self.target=();self.bad=False
  ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q618",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def on_set_level(self,l):self.stack=[];self.history=[];self.fault=0;self.target=compose(LEVELS[self.level_index]["message"]);self.bad=False
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3):self.stack.append(a);self.history.append(a)
  elif a==4:
   if len(self.stack)>=2:b=self.stack.pop();c=self.stack.pop();self.stack.append((c+2*b)%4);self.history.append(a)
   else:self.bad=True;self.lose()
  elif a==5:self.fault=(self.fault+1)%4
  elif a==6:
   if tuple(self.history)==x["message"] and tuple(self.stack)==self.target and self.fault==x["fault"]:self.next_level()
   else:self.bad=True;self.lose()
  else:self.bad=True;self.lose()
  self.complete_action()
